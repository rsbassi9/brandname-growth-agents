from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta
import json
import mimetypes
from pathlib import Path
import re
import shutil
import tempfile
from collections import Counter

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from .drive_service import GoogleDriveService
from .learning import FeedbackEntry, append_feedback, load_feedback
from .orchestrator import run_daily_workflow
from .performance import load_performance_records, performance_summary, save_performance_record
from .product_inventory import IMAGE_SUFFIXES, load_product_inventory, save_product_image
from .product_rotation import (
    prioritize_candidates_for_rotation,
    product_keys_for_names,
    product_rotation_note,
)
from .settings import OUTPUTS_DIR, ROOT_DIR
from .agents import content_candidate_agent, creative_composer_agent, feed_curator_agent, run_agent
from .asset_design_roles import asset_design_context
from .content_state import LIFECYCLE_STATES, get_content_state, load_content_state, update_content_state
from .campaign_memory import load_campaign_memory, save_campaign_memory, campaign_memory_context
from .creative_brief import load_creative_brief, save_creative_brief
from .file_store import save_markdown
from .image_concepts import generate_post_visual_image
from .shopify_service import ShopifyService
from .visual_fingerprint import grid_visual_warnings, visual_fingerprint_for_names
from .visual_metadata import metadata_for_output, warm_output_visual_metadata
from .visual_renderer import font_status, log_text_slide_edit, normalize_text_slides, render_text_carousel
from .web import product_catalog_summary


STATIC_DIR = ROOT_DIR / "dashboard" / "static"
CALENDAR_PATH = ROOT_DIR / "memory" / "content_calendar.json"
FEED_CURATION_PATH = ROOT_DIR / "memory" / "feed_curation.json"
REMOVED_CALENDAR_PATH = ROOT_DIR / "memory" / "removed_calendar_items.json"
CALENDAR_CHANGES_PATH = ROOT_DIR / "memory" / "calendar_changes.jsonl"
HIGHLIGHTS_PATH = ROOT_DIR / "memory" / "highlights.json"
CONTENT_PLAN_DIR = OUTPUTS_DIR / "content_plan"
SHOPIFY_SEO_LOG_PATH = ROOT_DIR / "memory" / "shopify_seo_changes.jsonl"
AUTOMATION_PATH = ROOT_DIR / "memory" / "automation_schedule.json"
AUTOMATION_LOG_PATH = ROOT_DIR / "memory" / "automation_log.jsonl"

app = FastAPI(title="Brand Name Growth Agents")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class FeedbackRequest(BaseModel):
    output_path: str
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    improvement_request: str = ""
    category: str = "general"


class ReviewRatingsRequest(BaseModel):
    ratings: list[FeedbackRequest]


class RegenerateRequest(BaseModel):
    source_path: str
    section: str = "caption"
    direction: str = ""


class DriveReplacementRequest(BaseModel):
    output_path: str
    drive_file_id: str
    drive_file_name: str
    mime_type: str


class CalendarUpdateRequest(BaseModel):
    scheduled_date: str | None = None
    status: str | None = None
    feed_position: int | None = None
    selected_assets: list[str] | None = None
    hook: str | None = None
    caption: str | None = None
    reviewer_notes: str | None = None


class CalendarSlotUpdateRequest(BaseModel):
    asset_name: str | None = None
    image_path: str | None = None
    role: str | None = None
    notes: str | None = None
    overlay_text: str | None = None


class FeedOrderRequest(BaseModel):
    ordered_ids: list[str]


class FeedCurateRequest(BaseModel):
    focus: str = "general"
    direction: str = ""


class HighlightFrameUpdateRequest(BaseModel):
    frame_index: int
    asset_name: str | None = None
    overlay_text: str | None = None
    role: str | None = None


class HighlightUpdateRequest(BaseModel):
    title: str | None = None
    purpose: str | None = None
    curator_note: str | None = None
    cover_asset_name: str | None = None
    reviewer_notes: str | None = None


class ContentStateUpdateRequest(BaseModel):
    item_type: str
    item_id: str
    status: str
    notes: str = ""
    title: str = ""
    metadata: dict = Field(default_factory=dict)


class PerformanceRecordRequest(BaseModel):
    post_id: str
    platform: str = "Instagram"
    post_url: str = ""
    posted_date: str = ""
    format: str = ""
    assets: list[str] = Field(default_factory=list)
    product_family: str = ""
    caption: str = ""
    hook: str = ""
    notes: str = ""
    metrics: dict = Field(default_factory=dict)


class CreativeBriefRequest(BaseModel):
    brief: dict = Field(default_factory=dict)
    note: str = ""


class AutomationConfigRequest(BaseModel):
    preset: str = "manual"
    enabled: bool = False
    review_required: bool = True
    notes: str = ""


class CampaignMemoryRequest(BaseModel):
    memory: dict = Field(default_factory=dict)
    source: str = "manual"


class ChecklistItemUpdateRequest(BaseModel):
    item_type: str
    item_id: str
    status: str | None = None
    title: str = ""
    detail: str = ""
    notes: str = ""
    metadata: dict = Field(default_factory=dict)


class VisualConceptRequest(BaseModel):
    direction: str = ""
    concept_type: str = "model_shoot"


class CreativeCompositionRequest(BaseModel):
    direction: str = ""


class TextSlideUpdateRequest(BaseModel):
    slides: list[dict] = Field(default_factory=list)


class ShootReferenceRequest(BaseModel):
    brief: str
    priority: str = "shoot_gap"
    direction: str = ""
    request: dict = Field(default_factory=dict)


class VisualNeedReferenceRequest(BaseModel):
    need: str
    direction: str = ""
    color_goal: str = ""


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/outputs")
def outputs() -> dict:
    return {"outputs": _collect_outputs()}


@app.get("/api/days")
def days() -> dict:
    return {"days": _collect_days()}


@app.get("/api/feedback")
def feedback() -> dict:
    return {"feedback": load_feedback()}


@app.get("/api/content-state")
def content_state() -> dict:
    return {"states": load_content_state(), "lifecycle_states": LIFECYCLE_STATES}


@app.get("/api/visual-metadata")
def visual_metadata() -> dict:
    return {"metadata": warm_output_visual_metadata()}


@app.get("/api/font-status")
def font_status_api() -> dict:
    return {"fonts": font_status()}


@app.post("/api/content-state")
def save_content_state_update(payload: ContentStateUpdateRequest) -> dict:
    if payload.status not in LIFECYCLE_STATES:
        raise HTTPException(status_code=400, detail="Unsupported lifecycle state")
    state_entry = update_content_state(
        item_type=payload.item_type,
        item_id=payload.item_id,
        status=payload.status,
        notes=payload.notes,
        title=payload.title,
        metadata=payload.metadata,
        source="dashboard",
    )
    _apply_state_to_native_item(payload.item_type, payload.item_id, payload.status, payload.notes)
    return {"state": state_entry, "states": load_content_state()}


@app.get("/api/product-inventory")
def product_inventory() -> dict:
    return {"products": load_product_inventory()}


@app.get("/api/product-context")
def product_context() -> dict:
    assets = GoogleDriveService().list_raw_assets()
    from .settings import BRAND_WEBSITE_URL

    return {"summary": product_catalog_summary(BRAND_WEBSITE_URL, assets)}


@app.get("/api/raw-assets")
def raw_assets(kind: str = "image") -> dict:
    assets = GoogleDriveService().list_raw_assets()
    if kind == "image":
        assets = [item for item in assets if item.get("mimeType") in {"image/jpeg", "image/png", "image/webp"}]
    elif kind == "video":
        assets = [item for item in assets if item.get("mimeType", "").startswith("video/")]
    return {"assets": assets}


@app.post("/api/product-inventory")
def upload_product_inventory(
    file: UploadFile = File(...),
    product_name: str = Form(""),
    notes: str = Form(""),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Upload must be a PNG, JPG, JPEG, or WEBP image")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        item = save_product_image(tmp_path, file.filename or "product-image", notes=notes, product_name=product_name)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"product": item, "products": load_product_inventory()}


@app.post("/api/feedback")
def save_feedback(payload: FeedbackRequest) -> dict:
    entry = FeedbackEntry(**payload.model_dump())
    return {"feedback": append_feedback(entry)}


@app.get("/api/review-items")
def review_items(date: str | None = None) -> dict:
    return {"items": _collect_review_items(date)}


@app.get("/api/action-checklists")
def action_checklists() -> dict:
    shopify = ShopifyService()
    return {
        "seo": _report_checklist("seo", shopify),
        "ads": _report_checklist("ad_concepts"),
        "shopify_status": shopify.status(),
    }


@app.get("/api/performance")
def performance() -> dict:
    records = load_performance_records()
    return {"records": records, "summary": performance_summary(records)}


@app.get("/api/creative-brief")
def creative_brief() -> dict:
    return load_creative_brief()


@app.get("/api/campaign-memory")
def campaign_memory() -> dict:
    return load_campaign_memory()


@app.post("/api/campaign-memory")
def save_campaign(payload: CampaignMemoryRequest) -> dict:
    return save_campaign_memory(payload.memory, payload.source)


@app.post("/api/campaign-memory/refresh")
def refresh_campaign_memory() -> dict:
    memory = _build_campaign_memory()
    return save_campaign_memory(memory, "dashboard_refresh")


@app.get("/api/shoot-plan")
def shoot_plan() -> dict:
    items = _load_calendar()
    strategy = _calendar_strategy(items)
    highlights = _load_highlights()
    return _build_shoot_plan(items, strategy, highlights)


@app.post("/api/shoot-plan/reference-image")
def shoot_reference_image(payload: ShootReferenceRequest) -> dict:
    item = {
        "id": f"shoot-reference-{_slugify(payload.priority)}",
        "format": "AI Reference",
        "pillar": "Shoot Gap",
        "hook": payload.brief[:120],
        "caption": "AI reference image for real photoshoot planning.",
        "source_files": [],
        "selected_assets": [],
    }
    try:
        concept_type = _reference_concept_type(payload.brief, payload.direction, payload.priority)
        concept = generate_post_visual_image(
            item=item,
            concept_type=concept_type,
            brief=payload.brief,
            direction=payload.direction or _reference_direction_for_type(concept_type),
            reference_paths=[],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reference generation failed: {exc}") from exc
    return {"concept": concept}


@app.post("/api/shoot-plan/calendar-placeholder")
def shoot_calendar_placeholder(payload: ShootReferenceRequest) -> dict:
    items = _load_calendar()
    before_by_id = {item.get("id"): dict(item) for item in items}
    request = payload.request or {}
    title = request.get("product") or payload.brief[:64] or "Shoot Gap"
    placeholder_id = f"shoot-placeholder-{_slugify(title)}"
    existing_ids = {item.get("id") for item in items}
    suffix = 2
    base_id = placeholder_id
    while placeholder_id in existing_ids:
        placeholder_id = f"{base_id}-{suffix}"
        suffix += 1
    scheduled = _next_open_date(date.today().isoformat(), {item.get("scheduled_date") for item in items if item.get("scheduled_date")})
    item = {
        "id": placeholder_id,
        "scheduled_date": scheduled,
        "status": "Needs Image",
        "platform": "Instagram",
        "format": "Shoot Placeholder",
        "pillar": "Shoot Gap",
        "hook": f"Need shoot: {title}",
        "caption": "",
        "source_files": [],
        "selected_assets": [],
        "visual_group": {},
        "visual_slots": [_empty_visual_slot(0)],
        "visual_role": "shoot_gap",
        "curator_reason": "Placeholder created from Shoot Planner so the calendar and feed can plan around a missing real asset.",
        "shoot_request": request,
        "shoot_brief": payload.brief,
        "calendar_note": "Needs real photoshoot asset. AI references are planning-only.",
        "feed_position": len(items),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    item["visual_slots"][0]["role"] = "campaign_anchor"
    item["visual_slots"][0]["notes"] = _shoot_request_summary(request) or payload.brief
    items.append(item)
    items = _save_calendar(items, sync_order="dates", change_source="shoot_placeholder", before_by_id=before_by_id)
    _save_content_plan(items)
    return {"item": next((entry for entry in items if entry.get("id") == placeholder_id), item), "items": items, "strategy": _calendar_strategy(items)}


@app.post("/api/visual-needs/reference-image")
def visual_need_reference_image(payload: VisualNeedReferenceRequest) -> dict:
    brief_parts = [
        payload.need,
        f"Color / feed goal: {payload.color_goal}" if payload.color_goal else "",
        payload.direction,
    ]
    brief = "\n".join(part for part in brief_parts if part).strip()
    item = {
        "id": f"visual-need-{_slugify(payload.need[:48])}",
        "format": "AI Reference",
        "pillar": "Curator Visual Need",
        "hook": payload.need[:120],
        "caption": "AI reference image for curator-directed feed planning.",
        "source_files": [],
        "selected_assets": [],
    }
    try:
        concept = generate_post_visual_image(
            item=item,
            concept_type="curator_process_reference",
            brief=brief,
            direction=(
                payload.direction
                or "Create a hyperrealistic process, studio, texture, color-breaker, or campaign-reference image. "
                "This is a visual planning reference, not an automatic final post."
            ),
            reference_paths=[],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Visual reference generation failed: {exc}") from exc
    return {"concept": concept}


@app.get("/api/merchandising")
def merchandising() -> dict:
    items = _load_calendar()
    assets = GoogleDriveService().list_raw_assets()
    strategy = _calendar_strategy(items)
    performance_data = performance_summary()
    shopify = ShopifyService().product_preview(limit=40)
    return _build_merchandising_plan(items, assets, strategy, performance_data, shopify)


@app.get("/api/drop-launch")
def drop_launch() -> dict:
    items = _load_calendar()
    highlights = _load_highlights()
    seo = _report_checklist("seo", ShopifyService())
    ads = _report_checklist("ad_concepts")
    shoot = _build_shoot_plan(items, _calendar_strategy(items), highlights)
    merch = _build_merchandising_plan(
        items,
        GoogleDriveService().list_raw_assets(),
        _calendar_strategy(items),
        performance_summary(),
        ShopifyService().product_preview(limit=20),
    )
    return _build_drop_launch_plan(items, highlights, seo, ads, shoot, merch)


@app.get("/api/community-faq")
def community_faq() -> dict:
    return _build_community_faq(_load_calendar(), _load_highlights(), _build_merchandising_plan(
        _load_calendar(),
        GoogleDriveService().list_raw_assets(),
        _calendar_strategy(_load_calendar()),
        performance_summary(),
        ShopifyService().product_preview(limit=20),
    ))


@app.get("/api/email-sms")
def email_sms() -> dict:
    return _build_email_sms_plan(_load_calendar(), merchandising(), drop_launch())


@app.get("/api/automation")
def automation() -> dict:
    return _load_automation()


@app.post("/api/automation")
def save_automation(payload: AutomationConfigRequest) -> dict:
    data = {
        "preset": payload.preset,
        "enabled": payload.enabled,
        "review_required": payload.review_required,
        "notes": payload.notes,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "external_changes": "Approval-gated",
    }
    AUTOMATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOMATION_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _append_automation_log("automation_config_updated", data)
    return _load_automation()


@app.post("/api/creative-brief")
def save_brief(payload: CreativeBriefRequest) -> dict:
    return save_creative_brief(payload.brief, payload.note)


@app.post("/api/performance")
def save_performance(payload: PerformanceRecordRequest) -> dict:
    records = save_performance_record(payload.model_dump())
    status = "Measured" if any(_metric_value(value) > 0 for value in payload.metrics.values()) else "Posted"
    update_content_state(
        item_type="post",
        item_id=payload.post_id,
        status=status,
        notes=payload.notes,
        title=payload.hook or payload.post_id,
        metadata={"performance_recorded": True, "post_url": payload.post_url, "posted_date": payload.posted_date},
        source="performance",
    )
    _apply_state_to_native_item("post", payload.post_id, status, payload.notes)
    return {"records": records, "summary": performance_summary(records), "states": load_content_state()}


def _metric_value(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _append_shopify_seo_log(item: dict, result: dict) -> None:
    SHOPIFY_SEO_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "item_id": item.get("id"),
        "title": item.get("title", ""),
        "action_type": item.get("action_type", ""),
        "status": item.get("status", ""),
        "result": result,
    }
    with SHOPIFY_SEO_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _load_automation() -> dict:
    config = {
        "preset": "manual",
        "enabled": False,
        "review_required": True,
        "notes": "",
        "external_changes": "Approval-gated",
    }
    if AUTOMATION_PATH.exists():
        try:
            config.update(json.loads(AUTOMATION_PATH.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    logs = []
    if AUTOMATION_LOG_PATH.exists():
        for line in AUTOMATION_LOG_PATH.read_text(encoding="utf-8").splitlines()[-40:]:
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {
        "config": config,
        "presets": [
            {"id": "manual", "label": "Manual only", "description": "Run when you click Run Today."},
            {"id": "daily_review", "label": "Daily review", "description": "Daily agent run, then user review before any changes."},
            {"id": "weekly_planning", "label": "Weekly planning", "description": "Weekly calendar/feed refresh and shoot planning."},
        ],
        "logs": list(reversed(logs)),
    }


def _append_automation_log(event_type: str, payload: dict) -> None:
    AUTOMATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {"created_at": datetime.now().isoformat(timespec="seconds"), "event_type": event_type, "payload": payload}
    with AUTOMATION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


@app.patch("/api/action-checklists/item")
def update_action_checklist_item(payload: ChecklistItemUpdateRequest) -> dict:
    if payload.item_type not in {"seo_action", "ad_action"}:
        raise HTTPException(status_code=400, detail="Unsupported checklist item type")
    if payload.status and payload.status not in LIFECYCLE_STATES:
        raise HTTPException(status_code=400, detail="Unsupported lifecycle state")
    state_entry = update_content_state(
        item_type=payload.item_type,
        item_id=payload.item_id,
        status=payload.status,
        title=payload.title,
        notes=payload.notes,
        metadata={"detail": payload.detail, **payload.metadata},
        source="checklist_edit",
    )
    return {"state": state_entry, "states": load_content_state()}


@app.get("/api/shopify/status")
def shopify_status() -> dict:
    return ShopifyService().status()


@app.get("/api/shopify/preview")
def shopify_preview() -> dict:
    return ShopifyService().product_preview()


@app.post("/api/shopify/seo-actions/apply")
def apply_shopify_seo_actions() -> dict:
    service = ShopifyService()
    checklist = _report_checklist("seo", service)
    approved = [item for item in checklist.get("items", []) if item.get("status") == "Approved"]
    results = []
    for item in approved:
        result = service.apply_seo_item(item)
        results.append(result)
        _append_shopify_seo_log(item, result)
        if result.get("applied"):
            update_content_state(
                item_type="seo_action",
                item_id=item["id"],
                status="Applied",
                title=item.get("title", ""),
                metadata={"detail": item.get("detail", ""), "shopify_result": result},
                source="shopify_seo_execution",
            )
    return {"approved_count": len(approved), "results": results, "states": load_content_state(), "shopify_status": service.status()}


@app.get("/api/highlights")
def highlights() -> dict:
    items = _load_highlights()
    if not items:
        items = _generate_highlights()
        _save_highlights(items)
    return {"highlights": items}


@app.post("/api/highlights/generate")
def generate_highlights() -> dict:
    items = _generate_highlights()
    _save_highlights(items)
    return {"highlights": items}


@app.patch("/api/highlights/{highlight_id}")
def update_highlight(highlight_id: str, payload: HighlightUpdateRequest) -> dict:
    highlights = _load_highlights()
    highlight = next((item for item in highlights if item.get("id") == highlight_id), None)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    before = dict(highlight)
    for field in ["title", "purpose", "curator_note", "cover_asset_name", "reviewer_notes"]:
        value = getattr(payload, field)
        if value is not None:
            highlight[field] = value.strip()
    highlight["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _record_highlight_edit(highlight, "highlight_update", before=before)
    _refresh_highlight_warnings(highlight)
    _save_highlights(highlights)
    return {"highlight": highlight, "highlights": highlights}


@app.post("/api/highlights/{highlight_id}/regenerate")
def regenerate_highlight(highlight_id: str) -> dict:
    highlights = _load_highlights()
    existing = next((item for item in highlights if item.get("id") == highlight_id), None)
    group = next((item for item in _highlight_groups() if item["id"] == highlight_id), None)
    if not group:
        raise HTTPException(status_code=404, detail="Highlight group not found")
    regenerated = _generate_highlight(group, _safe_raw_assets_for_rotation(), _load_calendar(), existing=existing)
    if existing:
        _record_highlight_edit(regenerated, "highlight_regenerate", before=existing)
    replaced = False
    for index, item in enumerate(highlights):
        if item.get("id") == highlight_id:
            highlights[index] = regenerated
            replaced = True
            break
    if not replaced:
        highlights.append(regenerated)
    _save_highlights(highlights)
    return {"highlight": regenerated, "highlights": highlights}


@app.post("/api/highlights/{highlight_id}/regenerate-cover")
def regenerate_highlight_cover(highlight_id: str) -> dict:
    highlights = _load_highlights()
    highlight = next((item for item in highlights if item.get("id") == highlight_id), None)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    before = dict(highlight)
    cover = _best_highlight_cover(highlight, _safe_raw_assets_for_rotation())
    if cover:
        highlight["cover_asset_name"] = cover
    highlight["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _record_highlight_edit(highlight, "highlight_cover_regenerate", before=before)
    _refresh_highlight_warnings(highlight)
    _save_highlights(highlights)
    return {"highlight": highlight, "highlights": highlights}


@app.patch("/api/highlights/{highlight_id}/frame")
def update_highlight_frame(highlight_id: str, payload: HighlightFrameUpdateRequest) -> dict:
    highlights = _load_highlights()
    highlight = next((item for item in highlights if item.get("id") == highlight_id), None)
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")
    frames = highlight.get("frames", [])
    if payload.frame_index < 0 or payload.frame_index >= len(frames):
        raise HTTPException(status_code=400, detail="Frame index out of range")
    before = dict(frames[payload.frame_index])
    if payload.asset_name is not None:
        frames[payload.frame_index]["asset_name"] = payload.asset_name
    if payload.overlay_text is not None:
        frames[payload.frame_index]["overlay_text"] = payload.overlay_text.strip()
    if payload.role is not None:
        frames[payload.frame_index]["role"] = payload.role.strip()
    frames[payload.frame_index]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _record_highlight_edit(
        highlight,
        "highlight_frame_update",
        before=before,
        extra={"frame_index": payload.frame_index, "after": frames[payload.frame_index]},
    )
    highlight["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _refresh_highlight_warnings(highlight)
    _save_highlights(highlights)
    return {"highlight": highlight, "highlights": highlights}


@app.post("/api/review-ratings")
def save_review_ratings(payload: ReviewRatingsRequest) -> dict:
    saved = []
    for rating in payload.ratings:
        saved.append(append_feedback(FeedbackEntry(**rating.model_dump())))
    items = _merge_calendar_edits(_generate_calendar_items(), _load_calendar())
    items = _save_calendar(items, sync_order="feed")
    plan_path = _save_content_plan(items)
    return {
        "saved": saved,
        "feedback": load_feedback(),
        "items": items,
        "strategy": _calendar_strategy(items),
        "curation": _curation_with_rationale(_load_feed_curation(), items),
        "plan_path": str(plan_path),
    }


@app.post("/api/run")
def run_agents() -> dict:
    paths = asyncio.run(run_daily_workflow())
    _append_automation_log("manual_run_complete", {"paths": paths})
    return {"paths": paths}


@app.get("/api/file")
def read_file(path: str) -> dict:
    resolved = _safe_output_path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Output not found")

    if resolved.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return {"path": str(resolved), "kind": "image", "url": f"/media?path={resolved}"}

    return {"path": str(resolved), "kind": "text", "content": resolved.read_text(encoding="utf-8")}


@app.get("/api/candidates")
def candidates(date: str | None = None) -> dict:
    path = _candidate_path(date)
    if not path:
        return {"candidates": []}
    return {"path": str(path), "candidates": _parse_candidates(path)}


@app.get("/api/calendar")
def calendar() -> dict:
    items = _load_calendar()
    if not items:
        items = _merge_calendar_edits(_generate_calendar_items(), [])
        items = _save_calendar(items, sync_order="feed")
        _save_content_plan(items)
    return {"items": items, "strategy": _calendar_strategy(items), "curation": _curation_with_rationale(_load_feed_curation(), items)}


@app.post("/api/calendar/generate")
def generate_calendar() -> dict:
    items = _merge_calendar_edits(_generate_calendar_items(), _load_calendar())
    items = _save_calendar(items, sync_order="feed")
    plan_path = _save_content_plan(items)
    return {"items": items, "strategy": _calendar_strategy(items), "plan_path": str(plan_path)}


@app.post("/api/calendar/launch-recovery")
def launch_recovery_calendar() -> dict:
    existing = _load_calendar() or _generate_calendar_items()
    recovery = _launch_recovery_items()
    existing = [item for item in existing if not str(item.get("id", "")).startswith("launch-recovery-")]
    start = date.today()
    combined = [*recovery, *existing]
    for index, item in enumerate(combined):
        item["scheduled_date"] = (start + timedelta(days=index)).isoformat()
        item["feed_position"] = index
        if index < len(recovery):
            item["calendar_note"] = "Launch recovery sequence scheduled before existing content."
    combined = _save_calendar(combined, sync_order="feed", change_source="launch_recovery")
    plan_path = _save_content_plan(combined)
    return {
        "items": combined,
        "strategy": _calendar_strategy(combined),
        "curation": _curation_with_rationale(_load_feed_curation(), combined),
        "plan_path": str(plan_path),
    }


@app.patch("/api/calendar/{item_id}")
def update_calendar_item(item_id: str, payload: CalendarUpdateRequest) -> dict:
    items = _load_calendar()
    before_by_id = {item.get("id"): dict(item) for item in items}
    schedule_changed = False
    for item in items:
        if item["id"] == item_id:
            before = dict(item)
            if payload.scheduled_date:
                item["scheduled_date"] = payload.scheduled_date
                schedule_changed = before.get("scheduled_date") != item.get("scheduled_date")
            if payload.status:
                item["status"] = payload.status
            if payload.feed_position is not None:
                item["feed_position"] = payload.feed_position
            if payload.selected_assets is not None:
                item["selected_assets"] = payload.selected_assets
            if payload.hook is not None:
                item["hook"] = payload.hook.strip()
            if payload.caption is not None:
                item["caption"] = payload.caption.strip()
            if payload.reviewer_notes is not None:
                item["reviewer_notes"] = payload.reviewer_notes.strip()
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            items = _save_calendar(
                items,
                sync_order="dates" if schedule_changed else None,
                change_source="manual_update",
                before_by_id=before_by_id,
            )
            _save_content_plan(items)
            updated = next((entry for entry in items if entry.get("id") == item_id), item)
            return {"item": updated, "items": items, "strategy": _calendar_strategy(items)}
    raise HTTPException(status_code=404, detail="Calendar item not found")


@app.patch("/api/calendar/{item_id}/slots/{slot_index}")
def update_calendar_slot(item_id: str, slot_index: int, payload: CalendarSlotUpdateRequest) -> dict:
    items = _load_calendar()
    before_by_id = {item.get("id"): dict(item) for item in items}
    for item in items:
        if item.get("id") != item_id:
            continue
        slots = _visual_slots_for_item(item)
        if slot_index < 0:
            raise HTTPException(status_code=400, detail="Slot index must be zero or greater")
        while len(slots) <= slot_index:
            slots.append(_empty_visual_slot(len(slots)))
        slot = slots[slot_index]
        before_slot = dict(slot)
        if payload.asset_name is not None:
            slot["asset_name"] = payload.asset_name.strip()
            slot["image_path"] = ""
            slot["source"] = "drive_asset"
            slot["name"] = payload.asset_name.strip()
        if payload.image_path is not None:
            slot["image_path"] = payload.image_path.strip()
            slot["source"] = "generated_visual"
            slot["name"] = Path(payload.image_path).name
        if payload.role is not None:
            slot["role"] = payload.role.strip()
        if payload.notes is not None:
            slot["notes"] = payload.notes.strip()
        if payload.overlay_text is not None:
            slot["overlay_text"] = payload.overlay_text.strip()
        slot["updated_at"] = datetime.now().isoformat(timespec="seconds")
        item["visual_slots"] = slots
        asset_names = [entry.get("asset_name", "").strip() for entry in slots if entry.get("asset_name", "").strip()]
        if asset_names:
            item["selected_assets"] = asset_names
        item.setdefault("edit_history", []).append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source": "slot_update",
                "slot_index": slot_index,
                "before": before_slot,
                "after": slot,
            }
        )
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        items = _save_calendar(items, change_source="slot_update", before_by_id=before_by_id)
        _save_content_plan(items)
        updated = next((entry for entry in items if entry.get("id") == item_id), item)
        return {"item": updated, "items": items, "strategy": _calendar_strategy(items), "slots": _visual_slots_for_item(updated)}
    raise HTTPException(status_code=404, detail="Calendar item not found")


@app.delete("/api/calendar/{item_id}")
def delete_calendar_item(item_id: str) -> dict:
    items = _load_calendar()
    remaining = [item for item in items if item.get("id") != item_id]
    if len(remaining) == len(items):
        raise HTTPException(status_code=404, detail="Calendar item not found")
    removed = _load_removed_calendar_items()
    if item_id not in removed:
        removed.append(item_id)
    _save_removed_calendar_items(removed)
    remaining = _save_calendar(remaining, sync_order="feed")
    plan_path = _save_content_plan(remaining)
    return {"items": remaining, "strategy": _calendar_strategy(remaining), "curation": _curation_with_rationale(_load_feed_curation(), remaining), "plan_path": str(plan_path)}


@app.post("/api/calendar/{item_id}/visual-concept")
async def create_visual_concept(item_id: str, payload: VisualConceptRequest) -> dict:
    items = _load_calendar()
    item = next((entry for entry in items if entry.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")

    candidate = _candidate_for_calendar_item(item)
    prompt = "\n\n".join(
        [
            "Create one AI image concept brief tied to this social post.",
            "The goal is visual direction for an Instagram/TikTok feed and future real photoshoots.",
            "Do not invent new products. If a garment appears, it must be based on the listed product/source files.",
            "Prefer realistic model/editorial concepts for product shots; prefer brush, pencil, canvas, digital-file, scanner, or studio-detail concepts for process posts.",
            "Return concise markdown with: Concept Title, Use Case, Image Prompt, Negative Prompt, Styling Notes, Feed Role, Source Assets To Respect.",
            f"Concept type: {payload.concept_type}",
            f"Reviewer direction: {payload.direction or 'Create a visually appealing concept that ties this post into the brand feed.'}",
            "Calendar post:",
            json.dumps(item, indent=2),
            "Candidate detail:",
            json.dumps(candidate or {}, indent=2),
            "Recent human feedback:",
            json.dumps([entry for entry in load_feedback(limit=40) if item_id in entry.get("output_path", "") or entry.get("category") in {"visual_content", "content_candidate"}], indent=2),
        ]
    )
    result = await run_agent(content_candidate_agent, prompt)
    path = save_markdown("image_concepts", f"{item_id}-{payload.concept_type}-visual-brief", result)
    image_result: dict[str, str] = {}
    image_error = ""
    try:
        image_result = generate_post_visual_image(
            item=item,
            concept_type=payload.concept_type,
            brief=result,
            direction=payload.direction,
            reference_paths=_reference_paths_for_item(item),
        )
    except Exception as exc:
        image_error = str(exc)

    concept = {
        "path": str(path),
        "image_path": image_result.get("image_path", ""),
        "metadata_path": image_result.get("metadata_path", ""),
        "concept_type": payload.concept_type,
        "direction": payload.direction,
        "image_error": image_error,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    item.setdefault("ai_visual_concepts", []).append(concept)
    item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_calendar(items)
    _save_content_plan(items)
    return {"item": item, "items": items, "concept": concept, "content": result, "image": image_result, "image_error": image_error}


@app.post("/api/calendar/{item_id}/compose")
async def compose_calendar_item(item_id: str, payload: CreativeCompositionRequest) -> dict:
    items = _load_calendar()
    item = next((entry for entry in items if entry.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")

    raw_assets = _safe_raw_assets_for_rotation()
    relevant_assets = _composition_relevant_assets(item, raw_assets)
    prompt = "\n\n".join(
        [
            "Create a premium creative composition plan for this single post.",
            "The plan must be based on real Drive/source assets and existing generated slides. Do not invent a final image.",
            "If the post is product-led, make it feel art-directed: hero, surface/backdrop, detail, transition, and CTA logic.",
            "Prefer folded textile/detail/mockup surfaces when useful for text or breathing room.",
            "Reviewer direction:",
            payload.direction or "Improve the design so this post feels premium and intentionally composed.",
            "Campaign memory:",
            campaign_memory_context(),
            "Calendar strategy:",
            json.dumps(_calendar_strategy(items), indent=2),
            "Post:",
            json.dumps(item, indent=2),
            "Relevant assets:",
            json.dumps(relevant_assets, indent=2),
            "Asset design role context:",
            asset_design_context(raw_assets),
        ]
    )
    raw = await run_agent(creative_composer_agent, prompt)
    plan = _extract_json_object(raw) or _fallback_composition_plan(item, relevant_assets, payload.direction)
    before_by_id = {entry.get("id"): dict(entry) for entry in items}
    item["composition_plan"] = plan
    item["composition_direction"] = payload.direction
    item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _apply_composition_to_slots(item, plan)
    item.setdefault("edit_history", []).append(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "creative_composition",
            "changes": {"composition_plan": True, "direction": payload.direction},
        }
    )
    items = _save_calendar(items, change_source="creative_composition", before_by_id=before_by_id)
    _save_content_plan(items)
    updated = next((entry for entry in items if entry.get("id") == item_id), item)
    return {"item": updated, "items": items, "plan": plan, "strategy": _calendar_strategy(items)}


@app.get("/api/calendar/{item_id}/text-slides")
def text_slides(item_id: str) -> dict:
    item = _calendar_item_or_404(item_id)
    return {"item_id": item_id, "slides": normalize_text_slides(item.get("text_slides", [])), "font_status": font_status()}


@app.patch("/api/calendar/{item_id}/text-slides")
def update_text_slides(item_id: str, payload: TextSlideUpdateRequest) -> dict:
    items = _load_calendar()
    before_by_id = {item.get("id"): dict(item) for item in items}
    for item in items:
        if item.get("id") != item_id:
            continue
        before_slides = normalize_text_slides(item.get("text_slides", []))
        slides = normalize_text_slides(payload.slides)
        item["text_slides"] = slides
        item["text_dominant"] = True
        item["visual_group"] = _launch_recovery_visual_group(item)
        item["selected_assets"] = []
        item["updated_at"] = datetime.now().isoformat(timespec="seconds")
        log_text_slide_edit(item_id, {"slides": before_slides, "launch_role": item.get("launch_role", "")}, {"slides": slides})
        items = _save_calendar(items, change_source="text_slide_edit", before_by_id=before_by_id)
        _save_content_plan(items)
        return {"item": item, "items": items, "slides": slides, "font_status": font_status()}
    raise HTTPException(status_code=404, detail="Calendar item not found")


@app.post("/api/calendar/{item_id}/visual-concept/iterate")
async def iterate_visual_concept(
    item_id: str,
    direction: str = Form(""),
    concept_type: str = Form("model_shoot"),
    base_image_path: str = Form(""),
    reference_files: list[UploadFile] | None = File(None),
) -> dict:
    items = _load_calendar()
    item = next((entry for entry in items if entry.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")

    upload_paths = _save_iteration_uploads(item_id, reference_files or [])
    base_path = _safe_output_path(base_image_path) if base_image_path else None
    reference_paths = _reference_paths_for_item(item)
    if base_path and base_path.exists():
        reference_paths.insert(0, base_path)
    reference_paths = upload_paths + reference_paths

    prior_concepts = [
        concept
        for concept in item.get("ai_visual_concepts", [])
        if not base_image_path or concept.get("image_path") == base_image_path or concept.get("path") == base_image_path
    ]
    prompt = "\n\n".join(
        [
            "Create a revised AI image concept brief for the selected post.",
            "Honor the prior image, but correct the requested issue. Keep product identity anchored to reference files.",
            "If the user references product branding, front logos, graphics, grommets, tags, hems, or other garment details, make those details visible in the revised image.",
            f"Concept type: {concept_type}",
            f"Reviewer revision request: {direction or 'Create a stronger iteration while preserving the product identity.'}",
            "Calendar post:",
            json.dumps(item, indent=2),
            "Prior concept metadata:",
            json.dumps(prior_concepts[-3:], indent=2),
        ]
    )
    result = await run_agent(content_candidate_agent, prompt)
    path = save_markdown("image_concepts", f"{item_id}-{concept_type}-iteration-brief", result)
    image_result: dict[str, str] = {}
    image_error = ""
    try:
        image_result = generate_post_visual_image(
            item=item,
            concept_type=f"{concept_type}_iteration",
            brief=result,
            direction=direction,
            reference_paths=reference_paths,
        )
    except Exception as exc:
        image_error = str(exc)

    concept = {
        "path": str(path),
        "image_path": image_result.get("image_path", ""),
        "metadata_path": image_result.get("metadata_path", ""),
        "concept_type": f"{concept_type}_iteration",
        "direction": direction,
        "base_image_path": base_image_path,
        "uploaded_reference_paths": [str(path) for path in upload_paths],
        "image_error": image_error,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    item.setdefault("ai_visual_concepts", []).append(concept)
    item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_calendar(items)
    _save_content_plan(items)
    return {"item": item, "items": items, "concept": concept, "content": result, "image": image_result, "image_error": image_error}


@app.post("/api/feed/reorder")
def reorder_feed(payload: FeedOrderRequest) -> dict:
    items = _load_calendar()
    before_by_id = {item.get("id"): dict(item) for item in items}
    order = {item_id: index for index, item_id in enumerate(payload.ordered_ids)}
    for item in items:
        if item["id"] in order:
            item["feed_position"] = order[item["id"]]
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    items = _save_calendar(items, sync_order="feed", change_source="feed_reorder", before_by_id=before_by_id)
    plan_path = _save_content_plan(items)
    return {"items": items, "strategy": _calendar_strategy(items), "curation": _curation_with_rationale(_load_feed_curation(), items), "plan_path": str(plan_path)}


@app.post("/api/feed/curate")
async def curate_feed(payload: FeedCurateRequest | None = None) -> dict:
    items = _load_calendar()
    if not items:
        items = _generate_calendar_items()
    before_by_id = {item.get("id"): dict(item) for item in items}
    candidates = _parse_candidates(_candidate_path()) if _candidate_path() else []
    strategy = _calendar_strategy(items)
    visual_warnings = strategy.get("visual_warnings", [])
    raw_assets = _safe_raw_assets_for_rotation()
    focus = (payload.focus if payload else "general") or "general"
    direction = (payload.direction if payload else "").strip()
    prompt = "\n\n".join(
        [
            "Curate the next Instagram feed grid using only these scheduled posts.",
            campaign_memory_context(),
            "Duplicate rule: never place exact duplicate asset sequences. If posts reuse the same images, only keep them if their order, role, and narrative purpose differ, and treat that as a last resort.",
            "Product rotation rule: avoid placing the same product family repeatedly across the grid. Give unused product families a turn before recently featured products unless the visual/story role changes clearly.",
            "Visual rhythm rule: use each post's visual_fingerprint to avoid clustering dark/black, text-heavy, dense digital/source, or visually similar posts together. If a row has multiple black/dark posts, split them unless the row concept deliberately needs that weight.",
            "Design-surface rule: folded cloth mockups, canvas/source textures, quiet product details, hems, tags, and negative-space product crops can be used as text backdrops, feed breakers, and carousel transition slides. Do not treat every product file as only a product hero.",
            "If focus is visual_warnings, prioritize fixing the listed visual rhythm warnings while preserving the strongest product/process/source story possible.",
            "Return strict JSON with the requested schema.",
            f"Curator focus: {focus}",
            f"Reviewer direction: {direction or 'Use the strongest brand-led grid rhythm.'}",
            "Visual rhythm warnings to fix:",
            json.dumps(visual_warnings, indent=2),
            "Asset design role context:",
            asset_design_context(raw_assets),
            "Scheduled posts:",
            json.dumps(items, indent=2),
            "Candidate details:",
            json.dumps(candidates, indent=2),
            "Strategy:",
            json.dumps(strategy, indent=2),
        ]
    )
    raw = await run_agent(feed_curator_agent, prompt)
    curation = _extract_json_object(raw) or _fallback_feed_curation(items)
    curation = _normalize_curation(curation, items)
    order = [entry["post_id"] for entry in curation.get("grid", [])]
    order_index = {item_id: index for index, item_id in enumerate(order)}
    for item in items:
        if item["id"] in order_index:
            item["feed_position"] = order_index[item["id"]]
            item["curator_reason"] = next((entry.get("reason", "") for entry in curation["grid"] if entry.get("post_id") == item["id"]), "")
            item["visual_role"] = next((entry.get("visual_role", "") for entry in curation["grid"] if entry.get("post_id") == item["id"]), "")
    items = _save_calendar(items, sync_order="feed", change_source="feed_curator", before_by_id=before_by_id)
    _save_feed_curation(curation)
    plan_path = _save_content_plan(items)
    return {"items": items, "strategy": _calendar_strategy(items), "curation": curation, "plan_path": str(plan_path)}


@app.post("/api/regenerate")
async def regenerate(payload: RegenerateRequest) -> dict:
    resolved = _safe_output_path(payload.source_path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")

    source = resolved.read_text(encoding="utf-8")
    prompt = "\n\n".join(
        [
            "Regenerate only the requested social content section.",
            f"Requested section: {payload.section}",
            f"Direction from reviewer: {payload.direction or 'Make it fresher, less corny, and more specific.'}",
            "Use only filenames and assets already present in the source candidate. Do not invent products or new assets.",
            "Keep the tone minimal, premium, art-first, and Instagram-ready.",
            "Source candidate/content:",
            source[:12000],
        ]
    )
    result = await run_agent(content_candidate_agent, prompt)
    path = save_markdown("content_variations", f"{payload.section}-variation", result)
    return {"path": str(path), "content": result}


@app.get("/media")
def media(path: str) -> FileResponse:
    resolved = _safe_output_path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=media_type)


@app.get("/product-media")
def product_media(path: str) -> FileResponse:
    resolved = Path(path).resolve()
    root = (ROOT_DIR / "brand_context" / "product_inventory").resolve()
    if resolved != root and root not in resolved.parents:
        raise HTTPException(status_code=400, detail="Path must be inside product inventory")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Product image not found")
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=media_type)


@app.get("/drive-media")
def drive_media(file_id: str, name: str, mime_type: str) -> FileResponse:
    previewable_mimes = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "video/quicktime", "video/mp4"}
    if mime_type not in previewable_mimes:
        raise HTTPException(status_code=400, detail="This Drive file type cannot be previewed")

    cache_dir = ROOT_DIR / ".cache" / "drive_media"
    cache_dir.mkdir(parents=True, exist_ok=True)
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "video/quicktime": ".mov",
        "video/mp4": ".mp4",
    }[mime_type]
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(name).stem).strip("-")[:60] or "drive-image"
    cached = cache_dir / f"{file_id}-{safe_name}{suffix}"
    if not cached.exists():
        GoogleDriveService().download_drive_file(file_id, cached)

    if mime_type in {"image/heic", "image/heif"}:
        converted = cache_dir / f"{file_id}-{safe_name}.jpg"
        if not converted.exists():
            _convert_heic_preview(cached, converted)
        return FileResponse(converted, media_type="image/jpeg")

    return FileResponse(cached, media_type=mime_type)


def _convert_heic_preview(source: Path, destination: Path) -> None:
    try:
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
    except ImportError as exc:
        raise HTTPException(
            status_code=415,
            detail="HEIC previews need pillow-heif. Install it with: python -m pip install pillow-heif",
        ) from exc

    try:
        with Image.open(source) as image:
            image.convert("RGB").save(destination, "JPEG", quality=90)
    except Exception as exc:
        raise HTTPException(status_code=415, detail="Could not convert HEIC preview") from exc


@app.post("/api/replace-image")
def replace_image(path: str, file: UploadFile = File(...)) -> dict:
    resolved = _safe_output_path(path)
    if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Only generated image files can be replaced")

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload must be an image")

    backup_dir = OUTPUTS_DIR / "_replaced_images"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{resolved.stem}-{timestamp}{resolved.suffix}"
    if resolved.exists():
        shutil.copy2(resolved, backup_path)

    with resolved.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    return {
        "path": str(resolved),
        "backup_path": str(backup_path) if backup_path.exists() else "",
        "url": f"/media?path={resolved}",
    }


@app.post("/api/replace-image-from-drive")
def replace_image_from_drive(payload: DriveReplacementRequest) -> dict:
    resolved = _safe_output_path(payload.output_path)
    if resolved.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Only generated image files can be replaced")
    if payload.mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Choose a JPG, PNG, or WEBP image from Drive")

    backup_dir = OUTPUTS_DIR / "_replaced_images"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{resolved.stem}-{timestamp}{resolved.suffix}"
    if resolved.exists():
        shutil.copy2(resolved, backup_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(payload.drive_file_name).suffix or ".img") as tmp:
        temp_path = Path(tmp.name)

    try:
        GoogleDriveService().download_drive_file(payload.drive_file_id, temp_path)
        with Image.open(temp_path) as image:
            converted = image.convert("RGB")
            if resolved.suffix.lower() in {".jpg", ".jpeg"}:
                converted.save(resolved, "JPEG", quality=92)
            elif resolved.suffix.lower() == ".webp":
                converted.save(resolved, "WEBP", quality=92)
            else:
                converted.save(resolved, "PNG")
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "path": str(resolved),
        "backup_path": str(backup_path) if backup_path.exists() else "",
        "url": f"/media?path={resolved}",
    }


def _collect_outputs() -> list[dict]:
    if not OUTPUTS_DIR.exists():
        return []

    files: list[Path] = []
    for path in OUTPUTS_DIR.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            files.append(path)

    results = []
    for path in sorted(files, key=lambda item: item.stat().st_mtime, reverse=True):
        rel = path.relative_to(ROOT_DIR)
        category = path.relative_to(OUTPUTS_DIR).parts[0]
        item = {
                "path": str(path),
                "relative_path": str(rel),
                "name": path.name,
                "category": category,
                "modified_at": path.stat().st_mtime,
                "kind": "image" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else "text",
            }
        if item["kind"] == "image":
            item["visual_metadata"] = metadata_for_output(path)
        _attach_state(item, "output", str(path))
        results.append(item)
    return results


def _collect_days() -> list[dict]:
    outputs = _collect_outputs()
    by_day: dict[str, list[dict]] = {}
    for item in outputs:
        day = _day_from_name(item["name"]) or _day_from_path(item["relative_path"])
        if not day:
            continue
        by_day.setdefault(day, []).append(item)

    days = []
    for day, items in sorted(by_day.items(), reverse=True):
        days.append(
            {
                "date": day,
                "reports": [item for item in items if item["category"] in {"daily_reports", "analytics", "seo", "ad_concepts", "asset_inventory"}],
                "copy": [item for item in items if item["category"] in {"content_ideas", "content_drafts", "content_candidates"}],
                "images": [item for item in items if item["kind"] == "image"],
                "visuals": _collect_visual_groups(day, items),
                "all_outputs": items,
            }
        )
    return days


def _collect_review_items(day: str | None = None) -> list[dict]:
    selected_day = day
    days = _collect_days()
    if not selected_day and days:
        selected_day = days[0]["date"]

    ratings = _feedback_rating_map()
    review: list[dict] = []
    candidate_path = _candidate_path(selected_day) if selected_day else _candidate_path()
    candidates = _parse_candidates(candidate_path) if candidate_path else []
    for candidate in candidates:
        review.append(
            {
                "id": f"candidate-{candidate['index']}",
                "type": "candidate",
                "title": candidate.get("hook") or candidate.get("title") or f"Candidate {candidate['index']}",
                "subtitle": f"{candidate.get('format') or 'Post'} / {candidate.get('pillar') or 'General'}",
                "path": f"{candidate['source_path']}#candidate-{candidate['index']}",
                "rating": ratings.get(f"{candidate['source_path']}#candidate-{candidate['index']}", 0),
                "category": "content_candidate",
                "candidate": candidate,
                "images": [],
            }
        )

    day_data = next((item for item in days if item["date"] == selected_day), None)
    if day_data:
        for group in day_data.get("visuals", []):
            group_path = _visual_group_path(group)
            rating = ratings.get(group_path) or max((ratings.get(image["path"], 0) for image in group.get("images", [])), default=0)
            review.append(
                {
                    "id": f"visual-{_slugify(group['name'])}",
                    "type": "visual_group",
                    "title": titleize(group["name"]),
                    "subtitle": f"{len(group.get('images', []))} visual slide{'s' if len(group.get('images', [])) != 1 else ''}",
                    "path": group_path,
                    "rating": rating,
                    "category": "visual_content",
                    "group": group,
                    "images": group.get("images", []),
                }
            )
        for output in day_data.get("reports", []):
            review.append(
                {
                    "id": f"report-{_slugify(output['relative_path'])}",
                    "type": "report",
                    "title": report_label(output),
                    "subtitle": output["name"],
                    "path": output["path"],
                    "rating": ratings.get(output["path"], 0),
                    "category": output["category"],
                    "images": [],
                }
            )

    return review


def _report_checklist(category: str, shopify: ShopifyService | None = None) -> dict:
    folder = OUTPUTS_DIR / category
    if not folder.exists():
        return {"source_path": "", "source_name": "", "items": []}
    reports = sorted(folder.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not reports:
        return {"source_path": "", "source_name": "", "items": []}
    path = reports[0]
    text = path.read_text(encoding="utf-8")
    items = _markdown_action_items(text, category, _slugify(path.stem))
    for item in items:
        _attach_state(item, "seo_action" if category == "seo" else "ad_action", item["id"])
        if category == "ad_concepts":
            item["ad_readiness"] = _ad_readiness(item)
    shopify_preview = {}
    if category == "seo":
        shopify_preview = (shopify or ShopifyService()).preview_for_items(items)
    return {
        "source_path": str(path),
        "source_name": path.name,
        "items": items,
        "shopify_status": shopify_preview.get("status") if shopify_preview else None,
    }


def _attach_state(item: dict, item_type: str, item_id: str, default_status: str | None = None) -> dict:
    if not item_id:
        return item
    state = get_content_state(item_type, item_id)
    if state:
        item["state"] = state
        item["status"] = state.get("status", item.get("status", default_status or "Draft"))
        if state.get("notes"):
            item["state_notes"] = state.get("notes")
        metadata = state.get("metadata", {})
        if metadata.get("detail"):
            item["detail"] = metadata["detail"]
        if metadata.get("action_type"):
            item["action_type"] = metadata["action_type"]
    elif default_status and not item.get("status"):
        item["status"] = default_status
    return item


def _markdown_action_items(text: str, category: str, source_slug: str = "latest") -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items = []
    for index, line in enumerate(lines):
        normalized = line.lstrip("-*0123456789. )").strip()
        if not normalized:
            continue
        lower = normalized.lower()
        is_action = (
            line.startswith(("-", "*"))
            or re.match(r"^\d+[\).]", line)
            or any(word in lower for word in ("update", "add", "write", "create", "optimize", "test", "improve", "fix", "launch", "prepare"))
        )
        if not is_action or len(normalized) < 12:
            continue
        items.append(
            {
                "id": f"{category}-{source_slug}-{index}",
                "status": "Needs Review",
                "title": normalized[:140],
                "detail": normalized,
                "action_type": _action_type(normalized, category),
                "risk": _action_risk(normalized, category),
                "requires_approval": True,
            }
        )
    return items[:18]


def _action_type(text: str, category: str) -> str:
    lower = text.lower()
    if category == "ad_concepts":
        if any(word in lower for word in ("creative", "image", "video", "reel")):
            return "ad_creative"
        if any(word in lower for word in ("budget", "campaign", "launch")):
            return "campaign_setup"
        return "ad_copy"
    if "alt text" in lower or ("image" in lower and "alt" in lower):
        return "image_alt_text"
    if "meta title" in lower or "title tag" in lower:
        return "meta_title"
    if "meta description" in lower:
        return "meta_description"
    if "product description" in lower or "description" in lower:
        return "product_description"
    if "product title" in lower or "rename" in lower:
        return "product_title"
    if "collection" in lower:
        return "collection_copy"
    if "homepage" in lower or "home page" in lower:
        return "homepage_copy"
    return "seo_action"


def _action_risk(text: str, category: str) -> str:
    lower = text.lower()
    if category == "ad_concepts" or any(word in lower for word in ("campaign", "budget", "spend", "publish", "launch")):
        return "High"
    if any(word in lower for word in ("theme", "code", "collection", "product description", "meta", "alt text")):
        return "Medium"
    return "Low"


def _ad_readiness(item: dict) -> dict:
    detail = f"{item.get('title', '')} {item.get('detail', '')}"
    lower = detail.lower()
    checks = {
        "creative_ready": any(word in lower for word in ("image", "video", "reel", "carousel", "creative", "asset", "visual")),
        "product_match": any(word in lower for word in ("product", "hoodie", "shirt", "tee", "tank", "grommet", "store", "shop")),
        "landing_page_ready": any(word in lower for word in ("landing", "product page", "collection", "shopify", "website", "url", "page")),
        "proof_available": any(word in lower for word in ("proof", "testimonial", "ugc", "review", "comment", "social", "views", "engagement")),
        "budget_risk": any(word in lower for word in ("budget", "spend", "campaign", "launch", "ad set", "cpm", "cpc")),
    }
    score = sum(1 for key, value in checks.items() if key != "budget_risk" and value) * 20
    if checks["budget_risk"]:
        score = max(0, score - 10)
    missing = [titleize(key) for key, value in checks.items() if key != "budget_risk" and not value]
    return {
        "score": min(score, 100),
        "checks": checks,
        "missing": missing,
        "required_creatives": _required_ad_creatives(lower),
        "copy_variants": _ad_copy_variants(item.get("title") or item.get("detail", "")),
        "cta_variants": _ad_cta_variants(lower),
        "mapped_destination": _ad_destination(lower),
        "launch_locked": True,
        "launch_note": "Launch/apply stays disabled until credentials, approvals, destination, and budget guardrails are intentionally added.",
    }


def _required_ad_creatives(lower: str) -> list[str]:
    if "reel" in lower or "video" in lower:
        return ["9:16 video cut", "cover frame", "short hook text", "product/detail cutaway"]
    if "carousel" in lower:
        return ["Slide 1 hook", "product/body slide", "detail proof slide", "CTA end slide"]
    return ["1:1 or 4:5 hero image", "product crop", "short primary text", "CTA variation"]


def _ad_copy_variants(seed: str) -> list[str]:
    base = seed.strip(" -:")[:90] or "Fine art reconstructed into wearable form."
    return [
        base,
        f"{base} Built for daily wear.",
        f"{base} Shop the current drop.",
    ]


def _ad_cta_variants(lower: str) -> list[str]:
    if "learn" in lower or "story" in lower:
        return ["Learn More", "View the Story", "Shop the Drop"]
    return ["Shop Now", "View Product", "Explore the Drop"]


def _ad_destination(lower: str) -> str:
    if "collection" in lower:
        return "Collection page"
    if any(word in lower for word in ("hoodie", "shirt", "tee", "tank", "product")):
        return "Matched product page"
    return "Brand homepage or drop landing page"


def _load_highlights() -> list[dict]:
    if not HIGHLIGHTS_PATH.exists():
        return []
    try:
        data = json.loads(HIGHLIGHTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    highlights = data if isinstance(data, list) else []
    for item in highlights:
        _attach_state(item, "highlight", item.get("id", ""))
    return highlights


def _apply_state_to_native_item(item_type: str, item_id: str, status: str, notes: str) -> None:
    if item_type == "post":
        items = _load_calendar()
        before_by_id = {item.get("id"): dict(item) for item in items}
        for item in items:
            if item.get("id") == item_id:
                item["status"] = status
                if notes:
                    item["reviewer_notes"] = notes
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                break
        _save_calendar(items, change_source="content_state", before_by_id=before_by_id)
        _save_content_plan(items)
        return

    if item_type == "highlight":
        highlights = _load_highlights()
        for item in highlights:
            if item.get("id") == item_id:
                item["status"] = status
                if notes:
                    item["reviewer_notes"] = notes
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                item.setdefault("edit_history", []).append(
                    {
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "source": "content_state",
                        "status": status,
                        "notes": notes,
                    }
                )
                break
        _save_highlights(highlights)


def _save_highlights(items: list[dict]) -> None:
    HIGHLIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    HIGHLIGHTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _generate_highlights() -> list[dict]:
    raw_assets = _safe_raw_assets_for_rotation()
    calendar_items = _load_calendar()
    existing_by_id = {item.get("id"): item for item in _load_highlights()}
    return [_generate_highlight(group, raw_assets, calendar_items, existing=existing_by_id.get(group["id"])) for group in _highlight_groups()]


def _highlight_groups() -> list[dict]:
    return [
        {
            "id": "new-drop",
            "title": "New Drop",
            "purpose": "Commercial product clarity with a strong campaign cover.",
            "buckets": ["Photoshoot / Campaign", "Store Products", "Shoot Photos"],
            "overlay_lines": ["NEW DROP", "DETAILS", "ON BODY", "AVAILABLE"],
        },
        {
            "id": "process",
            "title": "Process",
            "purpose": "Show evidence: studio, making, reconstruction, and detail.",
            "buckets": ["Process / Studio", "Design Assets", "Video"],
            "overlay_lines": ["PROCESS", "SOURCE", "RECONSTRUCT", "PROOF"],
        },
        {
            "id": "archive",
            "title": "Archive",
            "purpose": "Explain the source world and Adrift language.",
            "buckets": ["Design Assets", "Process / Studio", "Shoot Photos"],
            "overlay_lines": ["ARCHIVE", "FRAGMENT", "DRIFT", "OBJECT"],
        },
        {
            "id": "styling",
            "title": "Styling",
            "purpose": "Make the products wearable and easy to imagine in real life.",
            "buckets": ["Photoshoot / Campaign", "Shoot Photos", "Store Products"],
            "overlay_lines": ["STYLE", "FIT", "DETAIL", "WEAR"],
        },
        {
            "id": "q-and-a",
            "title": "Q&A",
            "purpose": "Answer brand, drop, sizing, shipping, and process questions.",
            "buckets": ["Design Assets", "Store Products", "Process / Studio"],
            "overlay_lines": ["Q&A", "WHAT IS 4DRFT?", "SIZING", "SHIPPING"],
        },
    ]


def _generate_highlight(group: dict, raw_assets: list[dict], calendar_items: list[dict], existing: dict | None = None) -> dict:
    assets = _highlight_assets_for_group(raw_assets, group["buckets"])
    frames = []
    for index, asset in enumerate(assets[:8]):
        frames.append(
            {
                "asset_name": asset.get("name", ""),
                "role": _highlight_frame_role(index, asset),
                "overlay_text": group["overlay_lines"][index % len(group["overlay_lines"])],
                "bucket": asset.get("creativeBucket", ""),
            }
        )
    if not frames:
        frames = _fallback_highlight_frames(calendar_items, group["overlay_lines"])
    title = existing.get("title") if existing else group["title"]
    purpose = existing.get("purpose") if existing else group["purpose"]
    cover_asset = existing.get("cover_asset_name") if existing and existing.get("cover_asset_name") else _best_highlight_cover({"frames": frames}, raw_assets) or (frames[0]["asset_name"] if frames else "")
    highlight = {
        "id": group["id"],
        "title": title or group["title"],
        "status": existing.get("status", "Draft") if existing else "Draft",
        "purpose": purpose or group["purpose"],
        "cover_asset_name": cover_asset,
        "frames": frames,
        "curator_note": existing.get("curator_note") if existing and existing.get("curator_note") else _highlight_curator_note(group["title"], frames),
        "reviewer_notes": existing.get("reviewer_notes", "") if existing else "",
        "edit_history": existing.get("edit_history", []) if existing else [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _refresh_highlight_warnings(highlight)
    _attach_state(highlight, "highlight", highlight["id"], "Draft")
    return highlight


def _highlight_assets_for_group(raw_assets: list[dict], buckets: list[str]) -> list[dict]:
    selected = []
    seen = set()
    for bucket in buckets:
        for asset in raw_assets:
            if asset.get("name") in seen:
                continue
            if asset.get("creativeBucket") != bucket:
                continue
            if not (asset.get("mimeType", "").startswith("image/") or asset.get("mimeType", "").startswith("video/")):
                continue
            selected.append(asset)
            seen.add(asset.get("name"))
    return selected


def _highlight_frame_role(index: int, asset: dict) -> str:
    bucket = asset.get("creativeBucket", "")
    if index == 0:
        if bucket == "Photoshoot / Campaign":
            return "campaign cover"
        return "cover"
    name = asset.get("name", "").lower()
    if bucket == "Photoshoot / Campaign":
        if any(term in name for term in ("detail", "close", "crop")):
            return "campaign detail"
        if any(term in name for term in ("full", "body", "look")):
            return "full-body campaign"
        return "campaign anchor"
    if bucket == "Store Products":
        return "product detail"
    if bucket in {"Photoshoot / Campaign", "Shoot Photos"}:
        return "body proof"
    if bucket == "Process / Studio":
        return "process proof"
    if bucket == "Video":
        return "motion beat"
    return "context"


def _fallback_highlight_frames(calendar_items: list[dict], overlay_lines: list[str]) -> list[dict]:
    frames = []
    names = []
    for item in sorted(calendar_items, key=lambda value: value.get("feed_position", 999)):
        for name in item.get("selected_assets") or item.get("source_files") or []:
            if name not in names:
                names.append(name)
    for index, name in enumerate(names[:6]):
        frames.append({"asset_name": name, "role": "planned post asset", "overlay_text": overlay_lines[index % len(overlay_lines)], "bucket": "Calendar"})
    return frames


def _best_highlight_cover(highlight: dict, raw_assets: list[dict]) -> str:
    frames = highlight.get("frames", [])
    by_name = {asset.get("name"): asset for asset in raw_assets}
    ranked = sorted(
        frames,
        key=lambda frame: _highlight_cover_rank(by_name.get(frame.get("asset_name", "")), frame),
    )
    return ranked[0].get("asset_name", "") if ranked else ""


def _highlight_cover_rank(asset: dict | None, frame: dict) -> tuple[int, str]:
    bucket = (asset or {}).get("creativeBucket") or frame.get("bucket", "")
    if bucket == "Photoshoot / Campaign":
        return (0, frame.get("asset_name", ""))
    if bucket == "Shoot Photos":
        return (1, frame.get("asset_name", ""))
    if bucket == "Store Products":
        return (2, frame.get("asset_name", ""))
    if bucket == "Design Assets":
        return (3, frame.get("asset_name", ""))
    if bucket == "Process / Studio":
        return (4, frame.get("asset_name", ""))
    return (5, frame.get("asset_name", ""))


def _refresh_highlight_warnings(highlight: dict) -> None:
    warnings = _highlight_warnings(highlight)
    highlight["warnings"] = warnings
    if highlight.get("status") in {"Approved", "Rejected", "Posted", "Measured", "Learned"}:
        return
    warning_types = {warning["type"] for warning in warnings}
    if "missing_frames" in warning_types:
        highlight["status"] = "Needs Frames"
    elif "weak_cover" in warning_types:
        highlight["status"] = "Needs Cover"
    elif warnings:
        highlight["status"] = "Needs Review"
    else:
        highlight["status"] = highlight.get("status") or "Draft"


def _highlight_warnings(highlight: dict) -> list[dict]:
    frames = highlight.get("frames", [])
    warnings = []
    if len(frames) < 4:
        warnings.append({"type": "missing_frames", "note": "Highlight needs at least four frames to feel useful."})
    buckets = Counter(frame.get("bucket", "") for frame in frames if frame.get("bucket"))
    if frames and buckets.get("Process / Studio", 0) > len(frames) / 2:
        warnings.append({"type": "too_much_process", "note": "Too many process frames. Add product, body, or source context for more pace."})
    if not any(frame.get("bucket") in {"Store Products", "Calendar"} or "product" in frame.get("role", "") for frame in frames):
        warnings.append({"type": "missing_product", "note": "Missing product/detail frame. Add a garment or product reference."})
    if not any(frame.get("bucket") in {"Photoshoot / Campaign", "Shoot Photos"} or "body" in frame.get("role", "") for frame in frames):
        warnings.append({"type": "missing_body", "note": "Missing body/campaign frame. Add a human or campaign anchor when available."})
    cover = highlight.get("cover_asset_name", "")
    cover_frame = next((frame for frame in frames if frame.get("asset_name") == cover), {})
    if not cover or cover_frame.get("bucket") in {"Process / Studio", "Video"}:
        warnings.append({"type": "weak_cover", "note": "Cover may be weak. Prefer campaign, body, product, or strong design asset as the hero image."})
    repeated = [bucket for bucket, count in buckets.items() if count >= 5]
    if repeated:
        warnings.append({"type": "repetitive_bucket", "note": f"Highlight leans heavily on {', '.join(repeated)}. Swap in contrasting frames."})
    return warnings


def _record_highlight_edit(highlight: dict, source: str, before: dict | None = None, extra: dict | None = None) -> None:
    entry = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
    }
    if before:
        entry["before"] = before
    if extra:
        entry.update(extra)
    highlight.setdefault("edit_history", []).append(entry)


def _highlight_curator_note(title: str, frames: list[dict]) -> str:
    if not frames:
        return "Add Drive assets to build this highlight."
    return f"{title} uses {len(frames)} frames. Keep the first frame as the strongest cover, then alternate product, body, process, and source context."


def report_label(item: dict) -> str:
    return titleize(item.get("category", "report"))


def _load_calendar() -> list[dict]:
    if not CALENDAR_PATH.exists():
        return []
    items = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    for item in items:
        if item.get("text_slides"):
            item["text_slides"] = normalize_text_slides(item.get("text_slides", []))
        item["visual_slots"] = _visual_slots_for_item(item)
        item["quality_score"] = _score_calendar_item(item)
        item["needs_work"] = _needs_work_reasons(item)
        _attach_state(item, "post", item.get("id", ""), item.get("status", "Draft"))
    return items


def _load_removed_calendar_items() -> list[str]:
    if not REMOVED_CALENDAR_PATH.exists():
        return []
    try:
        data = json.loads(REMOVED_CALENDAR_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_removed_calendar_items(items: list[str]) -> None:
    REMOVED_CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    REMOVED_CALENDAR_PATH.write_text(json.dumps(sorted(set(items)), indent=2), encoding="utf-8")


def _merge_calendar_edits(generated: list[dict], existing: list[dict]) -> list[dict]:
    removed = set(_load_removed_calendar_items())
    generated = [item for item in generated if item.get("id") not in removed]
    existing_by_id = {item.get("id"): item for item in existing}
    generated_ids = {item.get("id") for item in generated}
    preserved_fields = [
        "scheduled_date",
        "status",
        "feed_position",
        "selected_assets",
        "curator_reason",
        "visual_role",
        "updated_at",
    ]
    for item in generated:
        previous = existing_by_id.get(item.get("id"))
        if not previous:
            continue
        for field in preserved_fields:
            if field in previous:
                item[field] = previous[field]
    for item in existing:
        if item.get("id") not in generated_ids and item.get("id") not in removed:
            generated.append(item)
    return _ensure_one_post_per_day(_apply_duplicate_notes(_dedupe_calendar_items(generated)))


def _candidate_for_calendar_item(item: dict) -> dict | None:
    source_path = item.get("candidate_source_path")
    candidate_index = item.get("candidate_index")
    if not source_path or candidate_index is None:
        return None
    path = Path(source_path)
    if not path.exists():
        return None
    return next((candidate for candidate in _parse_candidates(path) if candidate.get("index") == candidate_index), None)


def _calendar_item_or_404(item_id: str) -> dict:
    item = next((entry for entry in _load_calendar() if entry.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    return item


def _asset_names_for_item(item: dict) -> list[str]:
    slot_names = [slot.get("asset_name", "") for slot in item.get("visual_slots", []) if slot.get("asset_name")]
    names = slot_names or item.get("selected_assets") or item.get("source_files") or []
    cleaned = []
    for name in names:
        text = str(name).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _composition_relevant_assets(item: dict, raw_assets: list[dict], limit: int = 28) -> list[dict]:
    names = set(item.get("selected_assets") or item.get("source_files") or [])
    product_keys = set(item.get("product_keys") or [])
    relevant = []
    for asset in raw_assets:
        product_match = any(key in str(asset.get("folderPath", "")).lower() for key in product_keys)
        design_match = {"text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker", "transition_slide"} & set(asset.get("designRoles", []))
        if asset.get("name") in names or product_match or design_match:
            relevant.append(
                {
                    "name": asset.get("name"),
                    "bucket": asset.get("creativeBucket"),
                    "folderPath": asset.get("folderPath"),
                    "designRoles": asset.get("designRoles", []),
                    "designSurfaceScore": asset.get("designSurfaceScore", 0),
                    "designUseNotes": asset.get("designUseNotes", ""),
                }
            )
    return sorted(relevant, key=lambda asset: (-int(asset.get("designSurfaceScore", 0)), asset.get("name", "")))[:limit]


def _fallback_composition_plan(item: dict, relevant_assets: list[dict], direction: str) -> dict:
    slots = _visual_slots_for_item(item)
    surface_assets = [
        asset
        for asset in relevant_assets
        if {"text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker", "transition_slide"} & set(asset.get("designRoles", []))
    ]
    slide_plan = []
    for index, slot in enumerate(slots):
        surface = surface_assets[index % len(surface_assets)] if surface_assets else {}
        asset_name = surface.get("name") if index > 0 and surface else slot.get("asset_name", "")
        slide_plan.append(
            {
                "slot": index,
                "role": "text_backdrop" if asset_name and index > 0 else slot.get("role", "hero"),
                "asset_name": asset_name,
                "image_path": slot.get("image_path", "") if not asset_name else "",
                "crop": "4:5 feed crop with intentional negative space.",
                "treatment": "Increase clarity, restrained contrast, slight texture/grain, avoid over-saturation.",
                "text_overlay": slot.get("overlay_text", ""),
                "reason": "Use design-surface assets to make the post feel composed instead of raw.",
            }
        )
    return {
        "summary": direction or "Premium product composition using hero, surface, detail, and transition logic.",
        "quality_bar": [
            "Clear hero image",
            "One quiet texture/backdrop surface",
            "Readable product identity",
            "No raw mockup dump",
        ],
        "slide_plan": slide_plan,
        "ai_reference_suggestions": [],
        "edit_notes": ["Review crop and text placement in Builder.", "Swap in folded textile/detail surfaces where the feed needs breathing room."],
    }


def _apply_composition_to_slots(item: dict, plan: dict) -> None:
    slots = _visual_slots_for_item(item)
    by_index = {int(entry.get("slot", index)): entry for index, entry in enumerate(plan.get("slide_plan", []))}
    for index, slot in enumerate(slots):
        entry = by_index.get(index)
        if not entry:
            continue
        if entry.get("asset_name"):
            slot["asset_name"] = entry.get("asset_name", "")
            slot["image_path"] = ""
            slot["source"] = "drive_asset"
            slot["name"] = entry.get("asset_name", slot.get("name", ""))
        elif entry.get("image_path"):
            slot["image_path"] = entry.get("image_path", "")
            slot["source"] = "generated_visual"
            slot["name"] = Path(entry.get("image_path", "")).name
        slot["role"] = entry.get("role") or slot.get("role", "supporting")
        slot["overlay_text"] = entry.get("text_overlay", slot.get("overlay_text", ""))
        slot["notes"] = " | ".join(part for part in [entry.get("crop", ""), entry.get("treatment", ""), entry.get("reason", "")] if part)
        slot["updated_at"] = datetime.now().isoformat(timespec="seconds")
    item["visual_slots"] = slots
    selected = [slot.get("asset_name", "") for slot in slots if slot.get("asset_name")]
    if selected:
        item["selected_assets"] = selected


def _empty_visual_slot(index: int) -> dict:
    return {
        "index": index,
        "name": f"Slot {index + 1}",
        "asset_name": "",
        "image_path": "",
        "source": "empty",
        "role": "supporting",
        "notes": "",
        "overlay_text": "",
    }


def _visual_slots_for_item(item: dict) -> list[dict]:
    existing = item.get("visual_slots")
    if isinstance(existing, list) and existing and not _should_refresh_visual_slots_from_group(item, existing):
        return [_normalize_visual_slot(slot, index) for index, slot in enumerate(existing)]

    visual_group = item.get("visual_group") if isinstance(item.get("visual_group"), dict) else {}
    visual_images = visual_group.get("images", [])
    if visual_images:
        slots = []
        for index, image in enumerate(visual_images):
            slots.append(
                _normalize_visual_slot(
                    {
                        "index": index,
                        "name": image.get("name") or Path(image.get("path", "")).name,
                        "image_path": image.get("path", ""),
                        "source": "generated_visual",
                        "role": "text_backdrop" if item.get("text_dominant") else _slot_role_from_item(item, index),
                        "notes": "Generated visual slide. Replace this slot with a Drive asset to hot swap the slide.",
                    },
                    index,
                )
            )
        return slots

    slots: list[dict] = []
    for index, name in enumerate(item.get("selected_assets") or item.get("source_files") or []):
        if not str(name).strip():
            continue
        slots.append(
            _normalize_visual_slot(
                {
                    "index": index,
                    "name": str(name),
                    "asset_name": str(name),
                    "source": "drive_asset",
                    "role": _slot_role_from_item(item, index),
                    "notes": "Original source asset slot.",
                },
                index,
            )
        )
    return slots


def _should_refresh_visual_slots_from_group(item: dict, existing: list[dict]) -> bool:
    visual_group = item.get("visual_group") if isinstance(item.get("visual_group"), dict) else {}
    if not visual_group.get("images"):
        return False
    if any(slot.get("updated_at") for slot in existing):
        return False
    source_names = set(item.get("source_files") or [])
    return bool(source_names) and all(slot.get("asset_name") in source_names for slot in existing if slot.get("asset_name"))


def _normalize_visual_slot(slot: dict, index: int) -> dict:
    return {
        "index": index,
        "name": slot.get("name") or slot.get("asset_name") or Path(slot.get("image_path", "")).name or f"Slot {index + 1}",
        "asset_name": slot.get("asset_name", ""),
        "image_path": slot.get("image_path", ""),
        "source": slot.get("source", "drive_asset" if slot.get("asset_name") else "generated_visual"),
        "role": slot.get("role", "supporting"),
        "notes": slot.get("notes", ""),
        "overlay_text": slot.get("overlay_text", ""),
        "updated_at": slot.get("updated_at", ""),
    }


def _slot_role_from_item(item: dict, index: int) -> str:
    if item.get("text_dominant"):
        return "text_backdrop"
    visual_role = item.get("visual_role") or item.get("pillar") or ""
    if visual_role:
        return str(visual_role).lower().replace(" ", "_")
    if index == 0:
        return "hero"
    return "supporting"


def _safe_raw_assets_for_rotation() -> list[dict]:
    try:
        return GoogleDriveService().list_raw_assets()
    except Exception:
        return []


def _ensure_product_keys(items: list[dict]) -> list[dict]:
    raw_assets = _safe_raw_assets_for_rotation()
    for item in items:
        names = item.get("selected_assets") or item.get("source_files") or []
        product_keys = sorted(product_keys_for_names(names, raw_assets))
        item["product_keys"] = product_keys
        item["product_rotation_note"] = product_rotation_note(product_keys, raw_assets)
        item["visual_fingerprint"] = visual_fingerprint_for_names(names, raw_assets)
    return items


def _ensure_quality_scores(items: list[dict]) -> list[dict]:
    for item in items:
        item["quality_score"] = _score_calendar_item(item)
        item["needs_work"] = _needs_work_reasons(item)
    return items


def _score_calendar_item(item: dict) -> dict:
    names = _asset_names_for_item(item)
    slots = _visual_slots_for_item(item)
    visual_group = item.get("visual_group") if isinstance(item.get("visual_group"), dict) else {}
    fingerprint = item.get("visual_fingerprint", {})
    product_keys = item.get("product_keys") or []
    has_visual = bool(names or visual_group.get("images") or any(slot.get("image_path") for slot in slots))
    designed_roles = {"text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker", "transition_slide", "hero", "product_clarity"}
    role_hits = sum(1 for slot in slots if slot.get("role") in designed_roles)
    has_composition = bool(item.get("composition_plan"))
    duplicate_penalty = 25 if item.get("duplicate_status") and item.get("duplicate_status") != "unique" else 0
    product_clarity = 85 if product_keys else (55 if item.get("pillar") in {"Product", "Drop CTA"} else 70)
    if item.get("format") == "Shoot Placeholder":
        product_clarity = 45
    brand_fit = 85 if item.get("launch_role") or item.get("curator_reason") else 68
    visual_freshness = 70
    if fingerprint.get("warnings"):
        visual_freshness -= min(25, len(fingerprint.get("warnings", [])) * 8)
    if role_hits:
        visual_freshness += min(15, role_hits * 4)
    feed_rhythm = 80 if item.get("feed_position") is not None else 60
    commercial = 85 if product_keys or "cta" in str(item.get("pillar", "")).lower() else 62
    designed = 88 if has_composition else 62 + min(18, role_hits * 5)
    if not has_visual:
        designed -= 25
        visual_freshness -= 20
    score = round((product_clarity + brand_fit + visual_freshness + feed_rhythm + commercial + designed) / 6 - duplicate_penalty)
    score = max(0, min(100, score))
    return {
        "overall": score,
        "product_clarity": max(0, min(100, product_clarity)),
        "brand_fit": max(0, min(100, brand_fit)),
        "visual_freshness": max(0, min(100, visual_freshness)),
        "feed_rhythm": max(0, min(100, feed_rhythm)),
        "commercial_usefulness": max(0, min(100, commercial)),
        "designed_vs_raw": max(0, min(100, designed)),
        "duplicate_risk": duplicate_penalty,
    }


def _needs_work_reasons(item: dict) -> list[dict]:
    score = item.get("quality_score") or _score_calendar_item(item)
    visual_group = item.get("visual_group") if isinstance(item.get("visual_group"), dict) else {}
    reasons = []
    if item.get("format") == "Shoot Placeholder" or item.get("status") == "Needs Image":
        reasons.append({"type": "needs_real_shoot_asset", "note": item.get("calendar_note", "Needs a real asset.")})
    if score.get("overall", 0) < 72:
        reasons.append({"type": "quality", "note": f"Overall quality score is {score.get('overall', 0)}. Run Improve Design or replace weak assets."})
    if score.get("designed_vs_raw", 0) < 72:
        reasons.append({"type": "needs_design_pass", "note": "Post may feel raw. Run Improve Design or add backdrop/detail slots."})
    if item.get("duplicate_status") and item.get("duplicate_status") != "unique":
        reasons.append({"type": "duplicate_risk", "note": item.get("duplicate_note", "Duplicate asset risk.")})
    if item.get("pillar") in {"Product", "Drop CTA"} and not item.get("product_keys"):
        reasons.append({"type": "product_unclear", "note": "Product-led post has no product family detected."})
    if not _asset_names_for_item(item) and not visual_group.get("images"):
        reasons.append({"type": "needs_image", "note": "No visual asset attached."})
    return reasons


def _shoot_request_summary(request: dict) -> str:
    fields = ["angle", "crop", "mood", "background", "lighting", "use_case", "solves"]
    return " | ".join(str(request.get(field, "")).strip() for field in fields if request.get(field))


def _ordered_asset_fingerprint(item: dict) -> str:
    return " > ".join(name.lower() for name in _asset_names_for_item(item))


def _asset_set_fingerprint(item: dict) -> str:
    return " + ".join(sorted(name.lower() for name in set(_asset_names_for_item(item))))


def _prior_asset_fingerprints() -> tuple[set[str], set[str]]:
    ordered: set[str] = set()
    unordered: set[str] = set()
    for path in sorted(CONTENT_PLAN_DIR.glob("*-plan.json"))[-12:]:
        if path.name.startswith(date.today().isoformat()):
            continue
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for post in plan.get("posts", []):
            assets = [str(name).strip() for name in post.get("source_files", []) if str(name).strip()]
            if not assets:
                continue
            ordered.add(" > ".join(name.lower() for name in assets))
            unordered.add(" + ".join(sorted(name.lower() for name in set(assets))))
    return ordered, unordered


def _dedupe_calendar_items(items: list[dict]) -> list[dict]:
    kept = []
    seen_ordered: set[str] = set()
    for item in sorted(items, key=lambda value: (value.get("feed_position", 999), value.get("created_at", ""))):
        ordered = _ordered_asset_fingerprint(item)
        if item.get("recovery_sequence"):
            kept.append(item)
            if ordered:
                seen_ordered.add(ordered)
            continue
        if ordered and ordered in seen_ordered:
            continue
        if ordered:
            seen_ordered.add(ordered)
        kept.append(item)
    return kept


def _apply_duplicate_notes(items: list[dict]) -> list[dict]:
    ordered_counts = Counter(_ordered_asset_fingerprint(item) for item in items if _ordered_asset_fingerprint(item))
    set_counts = Counter(_asset_set_fingerprint(item) for item in items if _asset_set_fingerprint(item))

    for item in items:
        ordered = _ordered_asset_fingerprint(item)
        unordered = _asset_set_fingerprint(item)
        item["asset_fingerprint"] = ordered
        item["asset_set_fingerprint"] = unordered
        existing_status = item.get("duplicate_status", "unique")
        item["duplicate_status"] = existing_status if existing_status == "previous_same_assets" else "unique"
        item["duplicate_note"] = item.get("duplicate_note", "") if item["duplicate_status"] != "unique" else ""

        if ordered and ordered_counts.get(ordered, 0) > 1:
            item["duplicate_status"] = "exact_duplicate"
            item["duplicate_note"] = "Exact same asset pairing and order appears more than once. Remove or change one post."
        elif unordered and set_counts.get(unordered, 0) > 1:
            item["duplicate_status"] = "same_assets_different_order"
            item["duplicate_note"] = "Same image set reused in a different order. Accept only as a last resort."
    return items


def _ensure_one_post_per_day(items: list[dict]) -> list[dict]:
    used_dates: set[str] = set()
    for item in sorted(items, key=lambda value: (value.get("scheduled_date") or "", value.get("feed_position", 999))):
        preferred = item.get("scheduled_date") or date.today().isoformat()
        scheduled = _next_open_date(preferred, used_dates)
        if scheduled != item.get("scheduled_date"):
            item["scheduled_date"] = scheduled
            item["calendar_note"] = "Auto-spaced so each post has its own day."
        used_dates.add(scheduled)
    return items


def _next_open_date(preferred: str, used_dates: set[str]) -> str:
    try:
        current = datetime.fromisoformat(preferred).date()
    except ValueError:
        current = date.today()
    while current.isoformat() in used_dates:
        current = current + timedelta(days=1)
    return current.isoformat()


def _sync_feed_positions_from_dates(items: list[dict]) -> list[dict]:
    for index, item in enumerate(sorted(items, key=lambda value: (value.get("scheduled_date") or "", value.get("feed_position", 999)))):
        item["feed_position"] = index
    return items


def _sync_dates_from_feed_positions(items: list[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda value: (value.get("feed_position", 999), value.get("scheduled_date") or ""))
    existing_dates = sorted({item.get("scheduled_date") for item in items if item.get("scheduled_date")})
    start = _date_from_iso(existing_dates[0]) if existing_dates else date.today()
    for index, item in enumerate(ordered):
        item["scheduled_date"] = (start + timedelta(days=index)).isoformat()
    return ordered


def _date_from_iso(value: str) -> date:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return date.today()


def _record_calendar_change(item: dict, before: dict, source: str) -> None:
    watched_fields = [
        "scheduled_date",
        "status",
        "feed_position",
        "selected_assets",
        "hook",
        "caption",
        "reviewer_notes",
        "curator_reason",
        "visual_role",
    ]
    changes = {}
    for field in watched_fields:
        if before.get(field) != item.get(field):
            changes[field] = {"before": before.get(field), "after": item.get(field)}
    if not changes:
        return

    entry = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "item_id": item.get("id"),
        "hook": item.get("hook", ""),
        "changes": changes,
    }
    CALENDAR_CHANGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CALENDAR_CHANGES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    item.setdefault("edit_history", []).append(entry)


def _reference_paths_for_item(item: dict) -> list[Path]:
    cache_dir = ROOT_DIR / ".cache" / "post_visual_references" / _slugify(item.get("id", "post"))
    paths: list[Path] = []

    wanted_names = set(item.get("selected_assets") or item.get("source_files") or [])
    if not wanted_names:
        return _visual_group_reference_paths(item, limit=4)

    try:
        assets = GoogleDriveService().list_raw_assets()
    except Exception:
        return _visual_group_reference_paths(item, limit=4)

    selected_assets = [asset for asset in assets if asset.get("name") in wanted_names]
    product_folders = {
        asset.get("folderPath", "")
        for asset in selected_assets
        if asset.get("creativeBucket") == "Store Products" and asset.get("folderPath")
    }
    reference_assets: list[dict] = []
    seen_ids: set[str] = set()

    # Product choices should bring their whole item folder, not only the 1-2 files
    # selected for the post. This gives the image model front/back/detail context.
    for folder in sorted(product_folders):
        folder_assets = [
            asset
            for asset in assets
            if asset.get("folderPath") == folder and asset.get("mimeType", "").startswith("image/")
        ]
        for asset in sorted(folder_assets, key=lambda value: _product_reference_rank(value, wanted_names)):
            if asset.get("id") and asset["id"] not in seen_ids:
                reference_assets.append(asset)
                seen_ids.add(asset["id"])

    for asset in selected_assets:
        if asset.get("id") in seen_ids or not asset.get("mimeType", "").startswith("image/"):
            continue
        reference_assets.append(asset)
        seen_ids.add(asset["id"])

    for asset in reference_assets[:12]:
        downloaded = _download_reference_asset(asset, cache_dir)
        if downloaded:
            paths.append(downloaded)

    paths.extend(_visual_group_reference_paths(item, limit=3))
    return _unique_paths(paths)[:12]


def _visual_group_reference_paths(item: dict, limit: int) -> list[Path]:
    paths = []
    for image in item.get("visual_group", {}).get("images", [])[:limit]:
        image_path = Path(image.get("path", ""))
        if image_path.exists():
            paths.append(image_path)
    return paths


def _product_reference_rank(asset: dict, wanted_names: set[str]) -> tuple[int, str]:
    name = asset.get("name", "")
    stem = Path(name).stem.lower()
    selected_rank = 0 if name in wanted_names else 1
    detail_rank = 0 if any(term in stem for term in ("front", "back", "detail", "mockup", "close")) else 1
    return (selected_rank, detail_rank, name.lower())


def _download_reference_asset(asset: dict, cache_dir: Path) -> Path | None:
    suffix = Path(asset.get("name", "")).suffix or ".img"
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", Path(asset.get("name", "reference")).stem).strip("-")[:80] or "reference"
    destination = cache_dir / f"{asset['id']}-{safe_stem}{suffix}"
    try:
        if not destination.exists():
            GoogleDriveService().download_drive_file(asset["id"], destination)
        return destination
    except Exception:
        return None


def _save_iteration_uploads(item_id: str, files: list[UploadFile]) -> list[Path]:
    upload_dir = ROOT_DIR / ".cache" / "post_visual_iteration_uploads" / _slugify(item_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, file in enumerate(files, start=1):
        content_type = file.content_type or ""
        suffix = Path(file.filename or "").suffix.lower()
        if not content_type.startswith("image/") and suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
            continue
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", file.filename or f"reference-{index}.img").strip("-")
        destination = upload_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{index}-{safe_name}"
        with destination.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        saved.append(destination)
    return saved


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _save_calendar(
    items: list[dict],
    sync_order: str | None = None,
    change_source: str | None = None,
    before_by_id: dict[str, dict] | None = None,
) -> list[dict]:
    CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    items = _ensure_product_keys(items)
    items = _ensure_quality_scores(items)
    for item in items:
        _attach_state(item, "post", item.get("id", ""), item.get("status", "Draft"))
    items = _apply_duplicate_notes(_dedupe_calendar_items(items))
    if sync_order == "feed":
        items = _sync_dates_from_feed_positions(items)
    items = _ensure_one_post_per_day(items)
    if sync_order == "dates":
        items = _sync_feed_positions_from_dates(items)
    items = _apply_duplicate_notes(items)
    items = _ensure_quality_scores(items)
    if change_source and before_by_id:
        for item in items:
            before = before_by_id.get(item.get("id"))
            if before:
                _record_calendar_change(item, before, change_source)
    CALENDAR_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return items


def _load_feed_curation() -> dict:
    if not FEED_CURATION_PATH.exists():
        return {}
    try:
        return json.loads(FEED_CURATION_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_feed_curation(curation: dict) -> None:
    FEED_CURATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEED_CURATION_PATH.write_text(json.dumps(curation, indent=2), encoding="utf-8")


def _curation_with_rationale(curation: dict, items: list[dict]) -> dict:
    if not curation:
        return {}
    normalized = _normalize_curation(curation, items)
    if not normalized.get("rationale"):
        normalized["rationale"] = _feed_curation_rationale(normalized.get("grid", []), items)
    return normalized


def _save_content_plan(items: list[dict]) -> Path:
    CONTENT_PLAN_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTENT_PLAN_DIR / f"{date.today().isoformat()}-plan.json"
    items = _apply_duplicate_notes(_dedupe_calendar_items(items))
    plan = {
        "date": date.today().isoformat(),
        "strategy": _calendar_strategy(items),
        "posts": [_post_plan_item(item) for item in sorted(items, key=lambda value: value.get("feed_position", 999))],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def _post_plan_item(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "platform": item.get("platform", "Instagram"),
        "format": item.get("format", "Post"),
        "pillar": item.get("pillar", "General"),
        "status": item.get("status", "Draft"),
        "scheduled_date": item.get("scheduled_date"),
        "feed_position": item.get("feed_position"),
        "hook": item.get("hook", ""),
        "caption": item.get("caption", ""),
        "source_files": item.get("selected_assets") or item.get("source_files", []),
        "original_source_files": item.get("source_files", []),
        "selected_assets": item.get("selected_assets", []),
        "visual_slots": _visual_slots_for_item(item),
        "product_keys": item.get("product_keys", []),
        "product_rotation_note": item.get("product_rotation_note", ""),
        "visual_fingerprint": item.get("visual_fingerprint", {}),
        "reviewer_notes": item.get("reviewer_notes", ""),
        "calendar_note": item.get("calendar_note", ""),
        "edit_history": item.get("edit_history", [])[-5:],
        "curator_reason": item.get("curator_reason", ""),
        "visual_role": item.get("visual_role", ""),
        "asset_fingerprint": item.get("asset_fingerprint") or _ordered_asset_fingerprint(item),
        "asset_set_fingerprint": item.get("asset_set_fingerprint") or _asset_set_fingerprint(item),
        "duplicate_status": item.get("duplicate_status", "unique"),
        "duplicate_note": item.get("duplicate_note", ""),
        "candidate_index": item.get("candidate_index"),
        "candidate_source_path": item.get("candidate_source_path"),
        "performance_notes": {},
    }


def _extract_json_object(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _normalize_curation(curation: dict, items: list[dict]) -> dict:
    valid_ids = {item["id"] for item in items}
    seen = set()
    grid = []
    for entry in curation.get("grid", []):
        post_id = entry.get("post_id")
        if post_id not in valid_ids or post_id in seen:
            continue
        seen.add(post_id)
        grid.append(
            {
                "post_id": post_id,
                "position": len(grid),
                "reason": entry.get("reason", ""),
                "visual_role": entry.get("visual_role", ""),
                "row_note": entry.get("row_note", ""),
            }
        )
    for item in sorted(items, key=lambda value: value.get("feed_position", 999)):
        if item["id"] not in seen:
            grid.append(
                {
                    "post_id": item["id"],
                    "position": len(grid),
                    "reason": "Kept in the remaining order after curator pass.",
                    "visual_role": _infer_visual_role(item),
                    "row_note": "Fills the grid rhythm.",
                }
            )
    return {
        "feed_story": curation.get("feed_story") or "Balance source, product, process, and body proof across the grid.",
        "rules": curation.get("rules") or [],
        "warnings": curation.get("warnings") or [],
        "grid": grid,
        "rationale": _feed_curation_rationale(grid, items),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _fallback_feed_curation(items: list[dict]) -> dict:
    role_order = {"body": 0, "product": 1, "source": 2, "process": 3, "meaning": 4, "motion": 5}
    decorated = []
    for item in items:
        role = _infer_visual_role(item)
        decorated.append((role_order.get(role, 9), item))
    grid = []
    last_role = ""
    for _, item in sorted(decorated, key=lambda value: (value[0], value[1].get("feed_position", 999))):
        role = _infer_visual_role(item)
        reason = "Adds visual contrast and keeps the story moving."
        if role == last_role:
            reason = "Placed here as a secondary option; consider swapping to avoid repetition."
        grid.append({"post_id": item["id"], "position": len(grid), "reason": reason, "visual_role": role, "row_note": "Fallback curator order."})
        last_role = role
    return {
        "feed_story": "Fallback curation: alternate product/body clarity with source/process context.",
        "rules": ["Avoid repeated visual roles side by side.", "Keep product or body proof visible every row."],
        "warnings": [],
        "grid": grid,
        "rationale": _feed_curation_rationale(grid, items),
    }


def _feed_curation_rationale(grid: list[dict], items: list[dict]) -> dict:
    item_by_id = {item.get("id"): item for item in items}
    ordered = sorted(grid, key=lambda entry: entry.get("position", 999))
    roles = [entry.get("visual_role") or _infer_visual_role(item_by_id.get(entry.get("post_id"), {})) for entry in ordered]
    row_notes = []
    for row_index in range(0, len(ordered), 3):
        row = ordered[row_index : row_index + 3]
        row_roles = [entry.get("visual_role") or _infer_visual_role(item_by_id.get(entry.get("post_id"), {})) for entry in row]
        row_notes.append(
            {
                "row": row_index // 3 + 1,
                "roles": row_roles,
                "note": _row_rationale(row_roles),
            }
        )
    column_notes = []
    for column in range(3):
        column_entries = ordered[column::3]
        column_roles = [entry.get("visual_role") or _infer_visual_role(item_by_id.get(entry.get("post_id"), {})) for entry in column_entries]
        column_notes.append(
            {
                "column": column + 1,
                "roles": column_roles[:8],
                "note": _column_rationale(column_roles, column + 1),
            }
        )
    return {
        "summary": _curation_summary(roles),
        "row_notes": row_notes,
        "column_notes": column_notes,
    }


def _curation_summary(roles: list[str]) -> str:
    counts = Counter(role or "unknown" for role in roles)
    dominant = ", ".join(f"{titleize(role)} x{count}" for role, count in counts.most_common(4))
    return f"Grid is arranged to balance visual roles across the profile. Current role mix: {dominant or 'not enough posts yet'}."


def _row_rationale(roles: list[str]) -> str:
    if not roles:
        return "Open row."
    if len(set(roles)) == len(roles):
        return "This row uses contrast between roles so the feed does not feel repetitive."
    return "This row repeats a role; review whether the image color, crop, or story is different enough."


def _column_rationale(roles: list[str], column: int) -> str:
    if not roles:
        return f"Column {column} has no posts yet."
    most_common = Counter(roles).most_common(1)[0]
    if most_common[1] >= max(3, len(roles) // 2):
        return f"Column {column} currently leans toward {most_common[0]}; this may be intentional, but watch repetition."
    return f"Column {column} is mixed to avoid locking the profile into one visual lane."


def _infer_visual_role(item: dict) -> str:
    text = " ".join([item.get("format", ""), item.get("pillar", ""), item.get("hook", ""), " ".join(item.get("source_files", []))]).lower()
    if "reel" in text or ".mov" in text:
        return "motion"
    if "jrr" in text:
        return "body"
    if "mockup" in text or "product" in text or "t-shirt" in text or "hoodie" in text:
        return "product"
    if "heic" in text or "process" in text or "studio" in text:
        return "process"
    if "adrift" in text or "painting" in text or "design" in text:
        return "source"
    return "meaning"


def _generate_calendar_items() -> list[dict]:
    raw_assets = _safe_raw_assets_for_rotation()
    candidates = prioritize_candidates_for_rotation(_recent_candidates(), raw_assets)
    visual_groups = []
    days = _collect_days()
    if days:
        visual_groups = days[0].get("visuals", [])
    prior_ordered, prior_sets = _prior_asset_fingerprints()
    seen_ordered: set[str] = set()

    start = date.today()
    items: list[dict] = []

    for index, candidate in enumerate(candidates):
        candidate_assets = candidate.get("source_files", [])
        product_keys = sorted(product_keys_for_names(candidate_assets, raw_assets))
        ordered_fingerprint = " > ".join(str(name).lower() for name in candidate_assets if str(name).strip())
        set_fingerprint = " + ".join(sorted(str(name).lower() for name in set(candidate_assets) if str(name).strip()))
        if ordered_fingerprint and (ordered_fingerprint in seen_ordered or ordered_fingerprint in prior_ordered):
            continue
        if ordered_fingerprint:
            seen_ordered.add(ordered_fingerprint)
        scheduled = start + timedelta(days=len(items))
        visual_group = _best_visual_group_for_candidate(candidate, visual_groups)
        candidate_id = f"candidate-{candidate['index']}" if index == 0 else f"candidate-{_day_from_path(candidate['source_path']) or index}-{candidate['index']}"
        duplicate_status = "previous_same_assets" if set_fingerprint and set_fingerprint in prior_sets else "unique"
        items.append(
            {
                "id": candidate_id,
                "scheduled_date": scheduled.isoformat(),
                "status": "Draft",
                "platform": "Instagram",
                "format": candidate.get("format") or "Post",
                "pillar": candidate.get("pillar") or "General",
                "hook": candidate.get("hook") or candidate.get("title") or "Draft post",
                "caption": candidate.get("caption", ""),
                "source_files": candidate.get("source_files", []),
                "product_keys": product_keys,
                "product_rotation_note": product_rotation_note(product_keys, raw_assets),
                "visual_fingerprint": visual_fingerprint_for_names(candidate_assets, raw_assets),
                "candidate_index": candidate["index"],
                "candidate_source_path": candidate["source_path"],
                "visual_group": visual_group,
                "feed_position": index,
                "selected_assets": candidate.get("source_files", []),
                "asset_fingerprint": ordered_fingerprint,
                "asset_set_fingerprint": set_fingerprint,
                "duplicate_status": duplicate_status,
                "duplicate_note": "These images were used together before. Reuse only with a different order, role, or story." if duplicate_status != "unique" else "",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    items.extend(_visual_calendar_items(visual_groups, len(items), start))
    return _apply_duplicate_notes(_dedupe_calendar_items(items))


def _recent_candidates(limit: int = 18) -> list[dict]:
    folder = OUTPUTS_DIR / "content_candidates"
    if not folder.exists():
        return []
    paths = sorted(folder.glob("*content-candidates.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    candidates: list[dict] = []
    for path in paths:
        candidates.extend(_parse_candidates(path))
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def _visual_calendar_items(visual_groups: list[dict], start_index: int, start: date) -> list[dict]:
    ratings = _feedback_rating_map()
    raw_assets = _safe_raw_assets_for_rotation()
    items = []
    for visual_index, group in enumerate(visual_groups):
        group_path = _visual_group_path(group)
        rating = ratings.get(group_path) or max((ratings.get(image["path"], 0) for image in group.get("images", [])), default=0)
        include_without_rating = visual_index < 8
        if rating < 4 and not include_without_rating:
            continue

        item_index = start_index + len(items)
        scheduled = start + timedelta(days=item_index)
        image_names = [image["name"] for image in group.get("images", [])]
        product_keys = sorted(product_keys_for_names(image_names, raw_assets))
        items.append(
            {
                "id": f"visual-{_slugify(group['name'])}",
                "scheduled_date": scheduled.isoformat(),
                "status": "Approved" if rating >= 4 else "Draft",
                "platform": "Instagram",
                "format": "Carousel" if len(group.get("images", [])) > 1 else "Solo Image Post",
                "pillar": "Visual Direction",
                "hook": titleize(group["name"]),
                "caption": "",
                "source_files": image_names,
                "product_keys": product_keys,
                "product_rotation_note": product_rotation_note(product_keys, raw_assets),
                "visual_fingerprint": visual_fingerprint_for_names(image_names, raw_assets),
                "candidate_index": None,
                "candidate_source_path": "",
                "visual_group": group,
                "feed_position": item_index,
                "selected_assets": [],
                "rating": rating,
                "review_path": group_path,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return items


def _launch_recovery_items() -> list[dict]:
    raw_assets = _safe_raw_assets_for_rotation()
    groups = _latest_visual_groups()
    source_assets = _launch_asset_names(raw_assets, ["adrift", "painting", "design", "canvas"], limit=3)
    origin_assets = source_assets[:2] if len(source_assets) >= 2 else source_assets
    product_sets = _launch_product_sets(raw_assets, limit_per_product=4)
    product_assets = [name for group in product_sets for name in group][:4] or _launch_asset_names(raw_assets, ["mockup", "hoodie", "shirt", "tee", "tank", "grommet"], limit=4)
    product_clarity_assets = product_sets[0][:2] if len(product_sets) > 0 else product_assets[:2]
    product_focus_assets = product_sets[1][:4] if len(product_sets) > 1 else product_assets[2:6] or product_assets
    cta_product_assets = product_sets[2][:2] if len(product_sets) > 2 else (product_sets[0][2:4] if product_sets else product_assets[:2])
    body_assets = _launch_asset_names(raw_assets, ["jrr", "photoshoot", "campaign", "model"], limit=4)
    process_assets = _launch_asset_names(raw_assets, ["heic", "process", "studio", "img_20", "img_19"], limit=4)
    motion_assets = _launch_asset_names(raw_assets, [".mov", "mov", "video"], limit=3)
    fallback_visual = [image["name"] for group in groups[:1] for image in group.get("images", [])[:3]]

    specs = [
        {
            "id": "launch-recovery-01-intro",
            "format": "Carousel",
            "pillar": "Drop Context",
            "hook": "What [4DRFT] actually is.",
            "caption": "One painting. Seven designs. A physical source reconstructed into wearable fragments.",
            "source_files": source_assets or fallback_visual,
            "visual_role": "meaning",
            "launch_role": "Intro / reset",
            "curator_reason": "This is the context reset that makes the drop legible before more product posts.",
            "on_screen_text": ["WHAT IS [4DRFT]?", "ONE PAINTING", "SEVEN DESIGNS", "RECONSTRUCTED TO WEAR"],
            "text_dominant": True,
            "text_slides": [
                {"eyebrow": "Drop reset", "headline": "WHAT IS [4DRFT]?", "body": "A new line built from one physical painting.", "palette": "dark"},
                {"eyebrow": "Source", "headline": "ONE PAINTING", "body": "The painting stays in the studio. The fragments move into the world.", "palette": "light"},
                {"eyebrow": "System", "headline": "SEVEN DESIGNS", "body": "Each garment carries a reconstructed piece of the original source.", "palette": "dark"},
                {"eyebrow": "Object", "headline": "RECONSTRUCTED TO WEAR", "body": "Not a graphic pasted on clothing. A source rebuilt as product.", "palette": "dark"},
            ],
        },
        {
            "id": "launch-recovery-02-origin",
            "format": "Carousel",
            "pillar": "Origin",
            "hook": "A physical painting. Reconstructed.",
            "caption": "The source stays in the studio. The fragments move into the world.",
            "source_files": origin_assets or fallback_visual[:2],
            "visual_role": "source",
            "launch_role": "Origin story",
            "curator_reason": "Source-first post explains the art system and gives the feed a clear narrative anchor.",
            "on_screen_text": ["CANVAS", "CAPTURE", "RECONSTRUCT", "DROP"],
            "text_dominant": True,
            "text_slides": [
                {"eyebrow": "01", "headline": "CANVAS", "body": "A physical painting begins the system.", "palette": "light"},
                {"eyebrow": "02", "headline": "CAPTURE", "body": "The source is documented, cropped, and studied.", "palette": "dark"},
                {"eyebrow": "03", "headline": "RECONSTRUCT", "body": "Fragments are rebuilt into garment-facing compositions.", "palette": "dark"},
                {"eyebrow": "04", "headline": "DROP", "body": "The final object enters the world as [4DRFT].", "palette": "light"},
            ],
        },
        {
            "id": "launch-recovery-03-product-clarity",
            "format": "Solo Image Post",
            "pillar": "Product",
            "hook": "The garment is the object.",
            "caption": "Product clarity after the origin story: the artwork becomes something wearable.",
            "source_files": product_clarity_assets or body_assets[:2] or fallback_visual[:2],
            "visual_role": "product",
            "launch_role": "Product clarity",
            "curator_reason": "Commercially clear product post prevents the launch from feeling only conceptual.",
            "on_screen_text": ["GARMENT OBJECT"],
        },
        {
            "id": "launch-recovery-04-body-proof",
            "format": "Reel",
            "pillar": "Wearability",
            "hook": "See it on body.",
            "caption": "Fit, scale, and movement make the reconstruction real.",
            "source_files": body_assets or motion_assets or product_assets[:2],
            "visual_role": "body",
            "launch_role": "Model / body proof",
            "curator_reason": "Body proof repairs the gap between concept and desire.",
            "on_screen_text": ["FIT", "SCALE", "MOVEMENT"],
        },
        {
            "id": "launch-recovery-05-process-proof",
            "format": "Carousel",
            "pillar": "Process",
            "hook": "The system is built, not styled.",
            "caption": "Process evidence: source, reconstruction, product detail.",
            "source_files": process_assets or source_assets or fallback_visual,
            "visual_role": "process",
            "launch_role": "Process proof",
            "curator_reason": "Process post gives credibility and breaks up product/body posts with evidence.",
            "on_screen_text": ["PROCESS", "PROOF", "SYSTEM"],
            "text_dominant": True,
            "text_slides": [
                {"eyebrow": "Process", "headline": "THE SYSTEM IS BUILT", "body": "Before product, there is evidence: source, crop, reconstruction, placement.", "palette": "dark"},
                {"eyebrow": "Proof", "headline": "NOT STYLED. BUILT.", "body": "Process frames make the garment feel intentional instead of random.", "palette": "light"},
                {"eyebrow": "Use", "headline": "SOURCE / OBJECT", "body": "These slides exist to slow the feed down and explain why the product matters.", "palette": "dark"},
            ],
        },
        {
            "id": "launch-recovery-06-product-focus",
            "format": "Carousel",
            "pillar": "Product",
            "hook": "Start with one piece.",
            "caption": "A focused product carousel: front, back, detail, context.",
            "source_files": product_focus_assets or body_assets or fallback_visual,
            "visual_role": "product",
            "launch_role": "Individual product focus",
            "curator_reason": "Begins the product-by-product ramp after the audience understands the line.",
            "on_screen_text": ["FRONT", "BACK", "DETAIL", "SOURCE"],
        },
        {
            "id": "launch-recovery-07-drop-cta",
            "format": "Solo Image Post",
            "pillar": "Drop CTA",
            "hook": "[4DRFT] is live.",
            "caption": "Fine art reconstructed. Shop the current drop.",
            "source_files": (body_assets[:1] + cta_product_assets) or fallback_visual,
            "visual_role": "meaning",
            "launch_role": "CTA / availability",
            "curator_reason": "Closes the recovery sequence by making the drop available and understandable.",
            "on_screen_text": ["[4DRFT]", "AVAILABLE NOW"],
        },
    ]

    items = []
    for index, spec in enumerate(specs):
        if spec.get("text_slides"):
            spec["text_slides"] = normalize_text_slides(spec["text_slides"])
        names = [name for name in spec["source_files"] if name]
        visual_group = _launch_recovery_visual_group(spec)
        selected_assets = [] if spec.get("text_dominant") and visual_group else names
        items.append(
            {
                **spec,
                "scheduled_date": (date.today() + timedelta(days=index)).isoformat(),
                "status": "Draft",
                "platform": "Instagram",
                "source_files": names,
                "selected_assets": selected_assets,
                "product_keys": sorted(product_keys_for_names(names, raw_assets)),
                "product_rotation_note": product_rotation_note(product_keys_for_names(names, raw_assets), raw_assets),
                "visual_fingerprint": visual_fingerprint_for_names([image["name"] for image in visual_group.get("images", [])] if visual_group else names, raw_assets),
                "visual_group": visual_group,
                "feed_position": index,
                "candidate_index": None,
                "candidate_source_path": "",
                "recovery_sequence": True,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return items


def _latest_visual_groups() -> list[dict]:
    days = _collect_days()
    return days[0].get("visuals", []) if days else []


def _launch_recovery_visual_group(spec: dict) -> dict:
    if not spec.get("text_dominant"):
        return {}
    paths = render_text_carousel(spec["id"], spec.get("text_slides") or [])
    return {
        "name": spec["id"],
        "images": [{"name": path.name, "path": str(path), "kind": "image", "category": "visual_content"} for path in paths],
    }


def _launch_asset_names(raw_assets: list[dict], needles: list[str], limit: int = 4) -> list[str]:
    found = []
    for asset in raw_assets:
        text = " ".join([str(asset.get("name", "")), str(asset.get("folderPath", "")), str(asset.get("creativeBucket", ""))]).lower()
        if any(needle.lower() in text for needle in needles):
            name = asset.get("name")
            if name and name not in found:
                found.append(name)
        if len(found) >= limit:
            break
    return found


def _launch_product_sets(raw_assets: list[dict], limit_per_product: int = 4) -> list[list[str]]:
    groups: dict[str, list[dict]] = {}
    for asset in raw_assets:
        if asset.get("creativeBucket") != "Store Products":
            continue
        key = _product_group_key(asset)
        if not key:
            continue
        groups.setdefault(key, []).append(asset)

    ordered_groups = sorted(
        groups.values(),
        key=lambda assets: (
            -max(int(asset.get("designSurfaceScore", 0)) for asset in assets),
            _product_group_key(assets[0]),
        ),
    )
    selected: list[list[str]] = []
    for assets in ordered_groups:
        assets = sorted(
            assets,
            key=lambda asset: (
                -int(asset.get("designSurfaceScore", 0)),
                _mockup_preference(asset.get("name", "")),
                asset.get("name", "").lower(),
            ),
        )
        names = []
        for asset in assets:
            name = asset.get("name", "")
            if name and name not in names:
                names.append(name)
            if len(names) >= limit_per_product:
                break
        if names:
            selected.append(names)
    return selected


def _product_group_key(asset: dict) -> str:
    folder = str(asset.get("folderPath", "")).replace("\\", "/")
    parts = [part for part in folder.split("/") if part]
    if "Products" in parts:
        index = parts.index("Products")
        if len(parts) > index + 1:
            return parts[index + 1].lower()
    return ""


def _mockup_number(name: str) -> int:
    match = re.search(r"mockups-(\d+)", name.lower())
    return int(match.group(1)) if match else 999


def _mockup_preference(name: str) -> int:
    number = _mockup_number(name)
    preferred = [9, 7, 8, 6, 1, 2, 3, 4, 5, 10]
    if number in preferred:
        return preferred.index(number)
    return 100 + number


def _reference_concept_type(brief: str, direction: str, priority: str) -> str:
    text = " ".join([brief, direction, priority]).lower()
    product_terms = ("product", "body", "worn", "wear", "model", "campaign", "fit", "garment", "shirt", "tee", "tank", "hoodie", "shorts")
    process_terms = ("brush", "pencil", "paint", "canvas", "studio", "process", "scanner", "design file")
    if any(term in text for term in product_terms) and not any(term in text for term in process_terms):
        return "model_shoot"
    if "feed breaker" in text or "color" in text or "texture" in text or "surface" in text:
        return "feed_breaker"
    if any(term in text for term in process_terms):
        return "process_detail"
    return "model_shoot"


def _reference_direction_for_type(concept_type: str) -> str:
    if concept_type == "model_shoot":
        return "Create a realistic product/editorial photoshoot reference using the named garment or product family. Show styling, crop, lighting, and body/product clarity. This is not final content."
    if concept_type == "feed_breaker":
        return "Create a premium feed-breaker reference: textile surface, canvas texture, color field, folded garment detail, or quiet negative-space composition. This is not final content."
    return "Create a premium process/studio detail reference: brush, pencil, canvas, scanner, design file, or tactile studio evidence. This is not final content."


def _feedback_rating_map() -> dict[str, int]:
    ratings = {}
    for item in load_feedback(limit=500):
        output_path = item.get("output_path")
        rating = item.get("rating")
        if output_path and isinstance(rating, int):
            ratings[output_path] = rating
    return ratings


def _visual_group_path(group: dict) -> str:
    images = group.get("images", [])
    if images:
        return str(Path(images[0]["path"]).parent)
    return group.get("name", "")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "visual"


def titleize(value: str) -> str:
    return re.sub(r"[-_]+", " ", value).strip().title()


def _best_visual_group_for_candidate(candidate: dict, visual_groups: list[dict]) -> dict | None:
    if not visual_groups:
        return None

    candidate_format = (candidate.get("format") or "").lower()
    if "carousel" in candidate_format:
        return max(visual_groups, key=lambda group: len(group.get("images", [])))
    if "reel" in candidate_format or "video" in candidate_format:
        return None
    return visual_groups[0]


def _calendar_strategy(items: list[dict]) -> dict:
    counts: dict[str, int] = {}
    pillars: dict[str, int] = {}
    product_counts: dict[str, int] = {}
    duplicate_warnings = []
    raw_assets = _safe_raw_assets_for_rotation()
    visual_warnings = grid_visual_warnings(items)
    photoshoot_gaps = _photoshoot_gap_warnings(items)
    design_surfaces = _design_surface_candidates(raw_assets)
    needs_work = _needs_work_queue(items)
    row_objectives = _feed_row_objectives(items)
    for item in items:
        counts[item.get("format", "Post")] = counts.get(item.get("format", "Post"), 0) + 1
        pillars[item.get("pillar", "General")] = pillars.get(item.get("pillar", "General"), 0) + 1
        product_keys = item.get("product_keys") or sorted(product_keys_for_names(_asset_names_for_item(item), raw_assets=[]))
        for product_key in product_keys:
            product_counts[product_key] = product_counts.get(product_key, 0) + 1
        if item.get("duplicate_status") and item.get("duplicate_status") != "unique":
            duplicate_warnings.append(
                {
                    "id": item.get("id"),
                    "status": item.get("duplicate_status"),
                    "note": item.get("duplicate_note"),
                    "assets": _asset_names_for_item(item),
                }
            )

    return {
        "mood": "Premium, archival, art-led streetwear with product desirability under the system language.",
        "rhythm": "Balance transformation proof, wearable product clarity, process evidence, and quieter meaning posts.",
        "format_mix": counts,
        "pillar_mix": pillars,
        "product_mix": product_counts,
        "product_rotation": _calendar_product_rotation_summary(product_counts),
        "performance": performance_summary(),
        "visual_warnings": visual_warnings,
        "photoshoot_gaps": photoshoot_gaps,
        "design_surface_candidates": design_surfaces,
        "needs_work": needs_work,
        "row_objectives": row_objectives,
        "quality_summary": _quality_summary(items),
        "guidance": [
            "Avoid clustering too many abstract/process posts back-to-back.",
            "Let product/wearability appear every 2-3 posts so the page stays commercially legible.",
            "Use transformation/carousel posts as anchor pieces in the grid.",
            "Use Reels for movement, proof, and first-two-second hooks.",
            "Never repeat the exact same image pairing in the same order. If images must be reused, change order, role, and narrative purpose.",
            "Rotate product families before reusing a recently featured garment unless the format or story is meaningfully different.",
            "Avoid clustering posts with the same palette, brightness, density, or visual family in one row unless the row intentionally needs that weight.",
            "Use Photoshoot / Campaign assets as premium body/campaign anchors once available.",
            "Use folded cloth, canvas, quiet product-detail crops, and negative-space mockups as text backdrops, transition slides, or feed breakers when the grid needs breathing room.",
        ],
        "duplicate_warnings": duplicate_warnings,
    }


def _needs_work_queue(items: list[dict]) -> list[dict]:
    queue = []
    for item in sorted(items, key=lambda value: value.get("feed_position", 999)):
        reasons = item.get("needs_work") or _needs_work_reasons(item)
        if not reasons:
            continue
        queue.append(
            {
                "id": item.get("id"),
                "scheduled_date": item.get("scheduled_date"),
                "hook": item.get("hook"),
                "score": (item.get("quality_score") or {}).get("overall", 0),
                "reasons": reasons[:4],
            }
        )
    return queue[:12]


def _quality_summary(items: list[dict]) -> dict:
    scores = [(item.get("quality_score") or _score_calendar_item(item)).get("overall", 0) for item in items]
    if not scores:
        return {"average": 0, "ready": 0, "needs_work": 0}
    return {
        "average": round(sum(scores) / len(scores)),
        "ready": len([score for score in scores if score >= 78]),
        "needs_work": len([score for score in scores if score < 72]),
    }


def _feed_row_objectives(items: list[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda value: value.get("feed_position", 999))
    objectives = []
    for row_index in range(0, min(len(ordered), 18), 3):
        row = ordered[row_index : row_index + 3]
        roles = [item.get("visual_role") or _infer_visual_role(item) for item in row]
        products = [", ".join(item.get("product_keys", [])) for item in row if item.get("product_keys")]
        objective = "Balance context, desire, and product clarity."
        if row_index == 0:
            objective = "First row should explain the drop while showing enough desirability to keep scrolling."
        elif "product" in roles:
            objective = "Use product clarity without letting the row become a raw catalog strip."
        elif "process" in roles:
            objective = "Use process proof as credibility and breathing room."
        objectives.append(
            {
                "row": row_index // 3 + 1,
                "post_ids": [item.get("id") for item in row],
                "roles": roles,
                "products": products,
                "objective": objective,
            }
        )
    return objectives


def _design_surface_candidates(raw_assets: list[dict]) -> list[dict]:
    candidates = [
        asset
        for asset in raw_assets
        if {"text_backdrop", "texture_backdrop", "canvas_surface", "feed_breaker", "transition_slide"} & set(asset.get("designRoles", []))
    ]
    candidates = sorted(candidates, key=lambda asset: (-int(asset.get("designSurfaceScore", 0)), asset.get("name", "").lower()))
    return [
        {
            "name": asset.get("name", ""),
            "bucket": asset.get("creativeBucket", ""),
            "roles": asset.get("designRoles", []),
            "score": asset.get("designSurfaceScore", 0),
            "use": asset.get("designUseNotes", ""),
        }
        for asset in candidates[:18]
    ]


def _calendar_product_rotation_summary(product_counts: dict[str, int]) -> str:
    if not product_counts:
        return "No product families detected in the current calendar yet. Product rotation will apply when Store Products assets are selected."
    ordered = sorted(product_counts.items(), key=lambda item: (-item[1], item[0]))
    mix = ", ".join(f"{product}: {count}" for product, count in ordered[:10])
    repeated = [product for product, count in ordered if count > 1]
    note = f"Current planned product mix: {mix}."
    if repeated:
        note += f" Watch repeated product families: {', '.join(repeated[:5])}."
    return note


def _photoshoot_gap_warnings(items: list[dict]) -> list[dict]:
    ordered = sorted(items, key=lambda item: item.get("feed_position", 999))
    first_grid = ordered[:12]
    campaign_items = [
        item
        for item in first_grid
        if item.get("visual_fingerprint", {}).get("visual_family") == "campaign photo"
        or any("photoshoot" in str(name).lower() or "campaign" in str(name).lower() or str(name).lower().startswith("jrr") for name in item.get("selected_assets") or item.get("source_files") or [])
    ]
    warnings = []
    if not campaign_items:
        warnings.append(
            {
                "type": "missing_campaign_anchor",
                "severity": "high",
                "note": "Next grid has no campaign/body anchor. Add a Photoshoot / Campaign or strong JRR asset to break up product/process/design tiles.",
                "suggested_action": "Upload/select one bright or body-led campaign photo for the first 9-12 grid positions.",
            }
        )
    elif len(campaign_items) < 2 and len(first_grid) >= 9:
        warnings.append(
            {
                "type": "low_campaign_presence",
                "severity": "medium",
                "note": "Next grid has only one campaign/body anchor. Add another shoot asset for better profile rhythm.",
                "suggested_action": "Place one campaign asset every 4-6 posts when possible.",
            }
        )
    return warnings


def _build_shoot_plan(items: list[dict], strategy: dict, highlights: list[dict]) -> dict:
    product_mix = strategy.get("product_mix", {})
    repeated_products = [product for product, count in product_mix.items() if count > 1]
    missing_products = _underused_products(product_mix)
    photoshoot_gaps = strategy.get("photoshoot_gaps", [])
    visual_warnings = strategy.get("visual_warnings", [])
    highlight_needs = []
    for highlight in highlights:
        for warning in highlight.get("warnings", [])[:2]:
            highlight_needs.append(f"{highlight.get('title', 'Highlight')}: {warning}")

    must_shoot = []
    if photoshoot_gaps:
        must_shoot.append(
            _shot_request(
                priority="Must Shoot",
                product="Best current product or drop anchor",
                angle="Full-body campaign hero",
                crop="4:5 feed crop plus 9:16 story crop",
                mood="Premium, body-led, calm but directional",
                background="Clean urban wall, studio concrete, or quiet architectural exterior",
                lighting="Soft directional daylight or controlled studio side light",
                use_case="Feed anchor, highlight cover, ad creative, product page lifestyle proof",
                solves=photoshoot_gaps[0].get("note", "Missing campaign/body anchor."),
            )
        )
    for product in missing_products[:3]:
        must_shoot.append(
            _shot_request(
                priority="Must Shoot",
                product=titleize(product),
                angle="Front, back, worn detail, and one movement frame",
                crop="4:5 product/body crop",
                mood="Commercially clear while keeping the archival system language",
                background="Neutral studio or quiet exterior",
                lighting="Even enough to read garment details",
                use_case="Product rotation, feed breathing room, SEO/product-page support",
                solves=f"Underused product family: {product}.",
            )
        )

    nice_to_have = [
        _shot_request(
            priority="Nice To Have",
            product="Process tools and source material",
            angle="Brush, pencil, design file, fabric detail, screen reconstruction",
            crop="Macro, flat lay, and vertical process crop",
            mood="Evidence-led, tactile, sparse",
            background="Studio desk or work surface",
            lighting="Low glare, high texture visibility",
            use_case="Carousel transition slides, stories, highlights",
            solves="Adds process proof between product-heavy posts.",
        ),
        _shot_request(
            priority="Nice To Have",
            product="Highest priority garment",
            angle="Walking or turning motion sequence",
            crop="9:16 Reel cover and first-frame hook",
            mood="Quiet movement, not trend-edit heavy",
            background="Architectural exterior or studio sweep",
            lighting="Consistent exposure across motion frames",
            use_case="Reel hooks, story frames, paid creative test",
            solves="Provides movement assets for Reels and ads.",
        ),
    ]
    if visual_warnings:
        nice_to_have.append(
            _shot_request(
                priority="Nice To Have",
                product="Light/negative-space breaker",
                angle="Bright product detail or model pause frame",
                crop="Square and 4:5",
                mood="Airy, restrained, cleaner than the dense black/process posts",
                background="Light wall, window light, or neutral set",
                lighting="Brighter midtone exposure",
                use_case="Breaks up dense feed rows",
                solves=visual_warnings[0].get("note", "Visual rhythm needs a lighter breaker image."),
            )
        )

    optional = [
        _shot_request(
            priority="Optional",
            product="Packaging, labels, texture, care/detail",
            angle="Close product evidence",
            crop="Story highlight and product page detail crop",
            mood="Documentary and useful",
            background="Neutral tabletop",
            lighting="Clean detail light",
            use_case="FAQ highlights, product trust, email/SMS assets",
            solves="Adds conversion support content.",
        )
    ]

    return {
        "summary": "Shot list generated from current feed, calendar, highlight, visual rhythm, and product-rotation gaps.",
        "must_shoot": must_shoot,
        "nice_to_have": nice_to_have,
        "optional": optional,
        "signals": {
            "photoshoot_gaps": photoshoot_gaps,
            "visual_warnings": visual_warnings,
            "highlight_needs": highlight_needs[:6],
            "repeated_products": repeated_products,
            "underused_products": missing_products,
        },
    }


def _underused_products(product_mix: dict[str, int]) -> list[str]:
    if not product_mix:
        return ["hoodie", "tee", "tank", "design detail"]
    lowest = sorted(product_mix.items(), key=lambda item: (item[1], item[0]))
    return [product for product, count in lowest if count <= 1]


def _shot_request(**kwargs: str) -> dict:
    return kwargs


def _build_merchandising_plan(
    items: list[dict],
    assets: list[dict],
    strategy: dict,
    performance_data: dict,
    shopify_preview: dict,
) -> dict:
    product_mix = strategy.get("product_mix", {})
    drive_products = _drive_product_counts(assets)
    performance_products = performance_data.get("product_mix", {})
    overused = [product for product, count in product_mix.items() if count > 1]
    underused = [product for product in drive_products if product not in product_mix or product_mix.get(product, 0) == 0]
    shopify_products = shopify_preview.get("products", [])

    recommendations = []
    for product in underused[:6]:
        recommendations.append(
            {
                "product": titleize(product),
                "priority": "Push",
                "reason": "Drive has product assets, but the current calendar has not used this product family yet.",
                "next_action": "Create one product clarity post and one body/campaign frame before repeating recently used products.",
                "asset_count": drive_products.get(product, 0),
                "calendar_count": product_mix.get(product, 0),
                "performance_count": performance_products.get(product, 0),
            }
        )
    for product in overused[:6]:
        recommendations.append(
            {
                "product": titleize(product),
                "priority": "Pause",
                "reason": "This product appears multiple times in the planned grid.",
                "next_action": "Do not repeat unless the format, image order, or story purpose is meaningfully different.",
                "asset_count": drive_products.get(product, 0),
                "calendar_count": product_mix.get(product, 0),
                "performance_count": performance_products.get(product, 0),
            }
        )
    for product in sorted(set(product_mix) - set(overused))[:4]:
        recommendations.append(
            {
                "product": titleize(product),
                "priority": "Maintain",
                "reason": "Product is present without obvious overuse.",
                "next_action": "Use performance results before deciding whether to scale.",
                "asset_count": drive_products.get(product, 0),
                "calendar_count": product_mix.get(product, 0),
                "performance_count": performance_products.get(product, 0),
            }
        )

    return {
        "summary": "Merchandising plan generated from Drive product folders, planned calendar mix, performance memory, and Shopify preview status.",
        "shopify_status": shopify_preview.get("status", {}),
        "drive_products": drive_products,
        "calendar_product_mix": product_mix,
        "performance_product_mix": performance_products,
        "shopify_products": shopify_products[:12],
        "recommendations": recommendations[:14],
        "warnings": _merchandising_warnings(overused, underused, shopify_preview.get("status", {})),
    }


def _drive_product_counts(assets: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in assets:
        for product_key in product_keys_for_names([asset.get("name", "")], assets):
            counts[product_key] = counts.get(product_key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _merchandising_warnings(overused: list[str], underused: list[str], shopify_status: dict) -> list[str]:
    warnings = []
    if overused:
        warnings.append(f"Repeated planned products: {', '.join(overused[:5])}.")
    if underused:
        warnings.append(f"Unused Drive product families available: {', '.join(underused[:5])}.")
    if not shopify_status.get("enabled"):
        warnings.append("Shopify read-only preview is not connected, so stock/sales-aware merchandising is not available yet.")
    return warnings


def _build_drop_launch_plan(
    items: list[dict],
    highlights: list[dict],
    seo: dict,
    ads: dict,
    shoot: dict,
    merch: dict,
) -> dict:
    ordered = sorted(items, key=lambda item: item.get("feed_position", 999))
    sequence = [
        _launch_step("Teaser", _first_by_pillar(ordered, "Meaning") or ordered[:1], "Set the world and source language."),
        _launch_step("Source Story", _first_by_pillar(ordered, "Transformation") or ordered[1:2], "Explain painting/source to garment logic."),
        _launch_step("Product Reveal", _first_by_pillar(ordered, "Product") or ordered[2:3], "Make the product commercially clear."),
        _launch_step("Model / Body Proof", [item for item in ordered if _has_campaign_or_body(item)][:1], "Show wearability and fit."),
        _launch_step("Detail / Process", _first_by_pillar(ordered, "Process") or ordered[3:4], "Show evidence, texture, making, or reconstruction."),
        _launch_step("Reel / Motion", [item for item in ordered if "reel" in (item.get("format", "").lower()) or "video" in (item.get("format", "").lower())][:1], "Use motion for reach and hook testing."),
        _launch_step("Highlight Update", highlights[:2], "Pin story frames and covers to profile navigation."),
        _launch_step("SEO Update", seo.get("items", [])[:3], "Approve and apply relevant product/search improvements."),
        _launch_step("Ads Readiness", ads.get("items", [])[:3], "Prepare ad creative only after organic proof."),
    ]
    readiness = {
        "calendar_posts": len(items),
        "approved_posts": len([item for item in items if item.get("status") == "Approved"]),
        "highlights": len(highlights),
        "seo_approved": len([item for item in seo.get("items", []) if item.get("status") == "Approved"]),
        "ads_ready": len([item for item in ads.get("items", []) if (item.get("ad_readiness") or {}).get("score", 0) >= 60]),
        "must_shoot": len(shoot.get("must_shoot", [])),
        "products_to_push": len([item for item in merch.get("recommendations", []) if item.get("priority") == "Push"]),
    }
    return {
        "summary": "Launch plan connects content sequence, profile curation, SEO, Ads readiness, merchandising, and shoot gaps.",
        "sequence": sequence,
        "readiness": readiness,
        "blockers": _drop_launch_blockers(readiness),
    }


def _launch_step(stage: str, source_items: list[dict], purpose: str) -> dict:
    return {
        "stage": stage,
        "purpose": purpose,
        "items": [
            {
                "id": item.get("id", ""),
                "title": item.get("hook") or item.get("title") or item.get("id", ""),
                "format": item.get("format", item.get("action_type", "")),
                "status": item.get("status", "Draft"),
                "date": item.get("scheduled_date", ""),
            }
            for item in source_items[:3]
        ],
    }


def _first_by_pillar(items: list[dict], pillar: str) -> list[dict]:
    return [item for item in items if pillar.lower() in str(item.get("pillar", "")).lower()][:1]


def _has_campaign_or_body(item: dict) -> bool:
    names = " ".join(_asset_names_for_item(item)).lower()
    return any(token in names for token in ("jrr", "model", "body", "photoshoot", "campaign"))


def _drop_launch_blockers(readiness: dict) -> list[str]:
    blockers = []
    if readiness.get("calendar_posts", 0) < 5:
        blockers.append("Need at least five scheduled posts for a credible launch rhythm.")
    if readiness.get("approved_posts", 0) < 3:
        blockers.append("Approve at least three launch posts before treating the sequence as ready.")
    if readiness.get("must_shoot", 0) > 0:
        blockers.append("Shoot Planner still has must-shoot gaps.")
    if readiness.get("seo_approved", 0) == 0:
        blockers.append("No SEO improvements are approved yet.")
    return blockers or ["No major launch blockers detected for the current barebones readiness model."]


def _build_community_faq(items: list[dict], highlights: list[dict], merch: dict) -> dict:
    product_focus = [
        item.get("product")
        for item in merch.get("recommendations", [])
        if item.get("priority") in {"Push", "Maintain"}
    ][:4]
    replies = [
        _faq_reply("Sizing", "How does it fit?", "Most pieces are styled for relaxed daily wear. Check the product page measurements first, then size up if you want a looser silhouette."),
        _faq_reply("Shipping", "Do you ship to Canada and the USA?", "Yes. Shipping is available to Canada and the USA. The checkout page will show the exact rate and timeline."),
        _faq_reply("Drop", "When is the next drop?", "The next release will be announced through the feed, stories, and highlights. The best place to watch is the current drop highlight."),
        _faq_reply("Process", "Is this based on original artwork?", "Yes. The work starts from fine art/source material, then gets reconstructed into garment-focused fragments."),
        _faq_reply("Product", "Which product should I look at first?", f"Start with {', '.join(product_focus) if product_focus else 'the current featured product'} if you want the clearest entry into the drop."),
    ]
    highlight_suggestions = [
        {"title": "Sizing", "frames": ["Fit note", "Measurement reminder", "DM us if between sizes"]},
        {"title": "Shipping", "frames": ["Canada / USA", "Checkout rates", "Tracking note"]},
        {"title": "Process", "frames": ["Source artwork", "Reconstruction", "Garment detail"]},
        {"title": "Drop", "frames": ["Current pieces", "Best product", "Availability"]},
    ]
    story_prompts = [
        "Ask us anything about fit.",
        "Which detail do you want to see closer?",
        "Source painting or finished garment first?",
        "Should the next post be process, product, or model shot?",
    ]
    return {
        "summary": "Community FAQ generated from product focus, highlights, and current calendar direction.",
        "replies": replies,
        "highlight_suggestions": highlight_suggestions,
        "story_prompts": story_prompts,
        "content_hooks": [
            "What this fragment came from.",
            "How the garment actually fits.",
            "Why the detail is placed there.",
            "What is available now.",
        ],
        "current_highlights": [{"id": item.get("id"), "title": item.get("title"), "status": item.get("status")} for item in highlights[:8]],
    }


def _faq_reply(category: str, question: str, reply: str) -> dict:
    return {"category": category, "question": question, "reply": reply}


def _build_campaign_memory() -> dict:
    items = _load_calendar()
    strategy = _calendar_strategy(items)
    curation = _curation_with_rationale(_load_feed_curation(), items)
    highlights = _load_highlights()
    shoot = _build_shoot_plan(items, strategy, highlights)
    merch = _build_merchandising_plan(
        items,
        GoogleDriveService().list_raw_assets(),
        strategy,
        performance_summary(),
        ShopifyService().product_preview(limit=20),
    )
    launch = _build_drop_launch_plan(items, highlights, _report_checklist("seo", ShopifyService()), _report_checklist("ad_concepts"), shoot, merch)

    launch_posts = [item for item in sorted(items, key=lambda post: post.get("feed_position", 999)) if item.get("recovery_sequence")]
    product_priorities = [item.get("product") for item in merch.get("recommendations", []) if item.get("priority") == "Push"][:6]
    visual_needs = [warning.get("note", "") for warning in strategy.get("visual_warnings", [])[:4]]
    visual_needs.extend([gap.get("note", "") for gap in strategy.get("photoshoot_gaps", [])[:3]])
    visual_needs.extend(
        [
            f"Use {item.get('name')} as a {', '.join(item.get('roles', [])[:2])} when the grid needs a text surface or breathing room."
            for item in strategy.get("design_surface_candidates", [])[:4]
        ]
    )

    return {
        "campaign_focus": "[4DRFT] launch recovery" if launch_posts else "Current content cycle",
        "active_narrative": "Explain one painting -> seven designs -> wearable fragments before isolated product selling.",
        "feed_objective": curation.get("rationale", {}).get("summary") or "Make the next grid feel intentional, clear, and product-aware.",
        "product_priorities": product_priorities,
        "visual_needs": [item for item in visual_needs if item],
        "calendar_commitments": [
            f"{len(launch_posts)} launch recovery posts scheduled first.",
            f"{len(items)} total planned posts in calendar.",
            strategy.get("product_rotation", ""),
            f"Quality average: {strategy.get('quality_summary', {}).get('average', 0)}. Needs-work posts: {strategy.get('quality_summary', {}).get('needs_work', 0)}.",
        ],
        "shoot_gaps": [item.get("solves", "") for item in shoot.get("must_shoot", [])[:5]],
        "row_objectives": [item.get("objective", "") for item in strategy.get("row_objectives", [])[:6]],
        "channel_implications": [
            launch.get("summary", ""),
            f"SEO approved: {launch.get('readiness', {}).get('seo_approved', 0)}.",
            f"Ads ready: {launch.get('readiness', {}).get('ads_ready', 0)}.",
        ],
        "avoid_list": [
            "Avoid random isolated product posts before the drop story is clear.",
            "Avoid repeating same image sets in the same order.",
            "Avoid rows dominated by black/source-heavy/process-heavy posts unless intentional.",
            "Avoid corny captions or generic streetwear language.",
        ],
        "summary": "Use campaign recovery as the operating brief: context first, then product clarity, body proof, process proof, product focus, and CTA. Future generated posts should fill feed gaps instead of acting as isolated ideas.",
    }


def _build_email_sms_plan(items: list[dict], merch: dict, launch: dict) -> dict:
    approved = [item for item in items if item.get("status") in {"Approved", "Scheduled", "Posted", "Measured"}]
    source_items = approved or sorted(items, key=lambda item: item.get("feed_position", 999))[:4]
    push_products = [item.get("product") for item in merch.get("recommendations", []) if item.get("priority") == "Push"][:3]
    subject_seed = push_products[0] if push_products else "4DRFT"
    return {
        "summary": "Email/SMS plan generated from current calendar, launch readiness, and merchandising focus.",
        "subject_lines": [
            f"{subject_seed}: fine art reconstructed",
            "A source fragment, rebuilt to wear",
            "The current drop, organized",
            "From canvas to garment",
        ],
        "preview_text": [
            "New product direction, process evidence, and the story behind the drop.",
            "A quieter look at the pieces and the system behind them.",
        ],
        "email_sections": [
            {"title": "Opening", "copy": "Fine art reconstructed into wearable fragments. Start with the source, then move into the object."},
            {"title": "Product Focus", "copy": f"Feature: {', '.join(push_products) if push_products else 'the current product focus'}."},
            {"title": "Process Proof", "copy": "Show the reconstruction, studio evidence, and the detail that makes the garment feel intentional."},
            {"title": "CTA", "copy": "Shop the current drop."},
        ],
        "sms_drafts": [
            "The current drop is live: fine art reconstructed into wearable fragments. Shop now.",
            "New 4DRFT pieces are ready. See the source, the process, and the garment.",
        ],
        "source_posts": [
            {"id": item.get("id"), "hook": item.get("hook"), "format": item.get("format"), "status": item.get("status")}
            for item in source_items[:6]
        ],
        "readiness": launch.get("readiness", {}),
    }


def _candidate_path(day: str | None = None) -> Path | None:
    folder = OUTPUTS_DIR / "content_candidates"
    if not folder.exists():
        return None
    candidates = sorted(folder.glob("*content-candidates.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if day:
        candidates = [path for path in candidates if path.name.startswith(day)]
    return candidates[0] if candidates else None


def _parse_candidates(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    starts = [match.start() for match in re.finditer(r"^###\s+\d+", text, flags=re.M)]
    if starts:
        starts.append(len(text))
        chunks = [text[starts[index] : starts[index + 1]] for index in range(len(starts) - 1)]
    else:
        chunks = [text]

    parsed = []
    for index, chunk in enumerate([item.strip() for item in chunks if item.strip()], start=1):
        title = chunk.splitlines()[0].strip("# ").strip()
        parsed.append(
            {
                "index": index,
                "title": _clean_candidate_title(title),
                "source_path": str(path),
                "format": _field_from_candidate(chunk, "Format"),
                "pillar": _field_from_candidate(chunk, "Content pillar"),
                "hook": _field_from_candidate(chunk, "Hook"),
                "caption": _field_from_candidate(chunk, "Caption"),
                "source_files": _list_after_label(chunk, "Source files"),
                "asset_roles": _field_from_candidate(chunk, "Asset roles"),
                "on_screen_text": _list_after_label(chunk, "On-screen text"),
                "structure": _candidate_structure(chunk),
                "edit_notes": _field_from_candidate(chunk, "Edit notes"),
                "why": _field_from_candidate(chunk, "Why this should work"),
                "posting_priority": _field_from_candidate(chunk, "Posting priority"),
                "body": chunk,
            }
        )
    return parsed


def _field_from_candidate(text: str, label: str) -> str:
    inline_pattern = rf"^\s*-?\s*(?:\*\*)?{re.escape(label)}:(?:\*\*)?\s*(.*?)\s*$"
    next_field_pattern = r"^\s*-?\s*(?:\*\*)?[A-Z][^:*]{1,60}:(?:\*\*)?\s*"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(inline_pattern, line)
        if not match:
            continue

        value = _clean_markdown_value(match.group(1))
        if value:
            return value

        collected = []
        for follow in lines[index + 1 :]:
            if re.match(next_field_pattern, follow) or follow.startswith("###") or follow.strip() == "---":
                break
            clean = _clean_markdown_value(follow)
            if clean:
                collected.append(clean)
        return "\n".join(collected).strip()

    return ""


def _list_after_label(text: str, label: str) -> list[str]:
    value = _field_from_candidate(text, label)
    if not value:
        return []
    if "," in value:
        return [_clean_markdown_value(item) for item in value.split(",") if item.strip()]
    return [_clean_markdown_value(line) for line in value.splitlines() if line.strip()]


def _candidate_structure(text: str) -> str:
    labels = [
        "Story structure",
        "Reel structure",
        "Carousel structure",
        "Video structure",
        "Feed structure",
        "Reel or carousel structure",
    ]
    for label in labels:
        value = _field_from_candidate(text, label)
        if value:
            return value
    return ""


def _clean_candidate_title(title: str) -> str:
    return re.sub(r"^\d+\)\s*", "", title).strip() or "Draft"


def _clean_markdown_value(value: str) -> str:
    cleaned = value.strip().removeprefix("-").strip()
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.rstrip("  ")
    return cleaned


def _collect_visual_groups(day: str, items: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for item in items:
        if item["category"] not in {"visual_content", "image_concepts"}:
            continue
        parts = Path(item["relative_path"]).parts
        if len(parts) < 3:
            continue
        if parts[0] == "outputs":
            if len(parts) < 4:
                continue
            group_name = parts[2]
        else:
            group_name = parts[1]
        group = groups.setdefault(
            group_name,
            {
                "name": group_name,
                "images": [],
                "briefs": [],
            },
        )
        if item["kind"] == "image":
            group["images"].append(item)
        else:
            group["briefs"].append(item)

    return sorted([group for group in groups.values() if group["images"]], key=lambda item: item["name"])


def _day_from_name(name: str) -> str | None:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return match.group(1) if match else None


def _day_from_path(path: str) -> str | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path)
    return match.group(1) if match else None


def _safe_output_path(path: str) -> Path:
    resolved = Path(path).resolve()
    output_root = OUTPUTS_DIR.resolve()
    if resolved == output_root or output_root in resolved.parents:
        return resolved
    raise HTTPException(status_code=400, detail="Path must be inside outputs")
