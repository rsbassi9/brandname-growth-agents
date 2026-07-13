"""In-process async job queue (P1-4).

Single asyncio worker started in the FastAPI lifespan. Jobs are persisted in
the `jobs` table; results in `result_json`. Job kinds: generate_asset,
run_daily_workflow, render_carousel, image_iterate, brain_index,
distill_brand_profile, seo_audit, seo_fix, seo_plan, repurpose_shoot,
recycle_top_posts.

The run_daily_workflow handler checks LOCAL_ONLY_AGENT_RUNS and uses the
deterministic port of src/local_workflow.py when true — this closes the legacy
defect where `python -m src.orchestrator` ignored the flag.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from ..db import init_db, session_scope
from ..models import Asset, AssetVersion, CalendarItem, Campaign, Job, PostMetric, PublishedPost, SourceAsset
from ..settings import get_settings

logger = logging.getLogger(__name__)

JOB_KINDS = (
    "generate_asset",
    "run_daily_workflow",
    "render_carousel",
    "image_iterate",
    "brain_index",
    "distill_brand_profile",
    "seo_audit",
    "seo_fix",
    "seo_plan",
    "repurpose_shoot",
    "recycle_top_posts",
)


class JobQueue:
    def __init__(self) -> None:
        # The asyncio.Queue is created inside start(): it must be bound to the
        # lifespan's event loop (a fresh one per TestClient in tests).
        self._queue: asyncio.Queue[str] | None = None
        self._worker_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: list[str] = []

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        for job_id in self._pending:
            self._queue.put_nowait(job_id)
        self._pending.clear()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker(), name="job-worker")

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        self._loop = None
        self._queue = None

    def enqueue(self, kind: str, payload: dict[str, Any]) -> str:
        if kind not in JOB_KINDS:
            raise ValueError(f"Unknown job kind: {kind}")
        job_id = uuid.uuid4().hex
        with session_scope() as session:
            session.add(
                Job(
                    id=job_id,
                    kind=kind,
                    status="queued",
                    progress_pct=0,
                    message="queued",
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
        # Sync endpoints run in the threadpool, but the worker waits on the
        # queue inside the event loop: hand off thread-safely via the loop.
        loop, queue = self._loop, self._queue
        if loop is not None and queue is not None and loop.is_running():
            loop.call_soon_threadsafe(queue.put_nowait, job_id)
        else:
            # Not started yet: buffered and drained on the next start().
            self._pending.append(job_id)
        return job_id

    async def _worker(self) -> None:
        queue = self._queue
        assert queue is not None, "start() creates the queue before the worker runs"
        while True:
            job_id = await queue.get()
            try:
                await self._run_job(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                # The job row already records the failure; the worker must
                # survive to serve the next job.
                logger.exception("Job %s crashed", job_id)
            finally:
                queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                logger.error("Job %s vanished before execution", job_id)
                return
            kind = job.kind
            payload = json.loads(job.payload_json or "{}")

        _update_job(job_id, status="running", progress_pct=5, message="started")
        try:
            handler = _HANDLERS[kind]
            result = await handler(job_id, payload)
        except Exception as exc:
            logger.exception("Job %s (%s) failed", job_id, kind)
            _update_job(
                job_id,
                status="failed",
                progress_pct=100,
                message=f"{type(exc).__name__}: {exc}",
                finished_at=datetime.utcnow(),
            )
            return
        _update_job(
            job_id,
            status="succeeded",
            progress_pct=100,
            message="done",
            result_json=json.dumps(result, ensure_ascii=False),
            finished_at=datetime.utcnow(),
        )


async def run_one_shot(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one queued job to completion for CI/cron entry points."""
    init_db()
    await job_queue.start()
    try:
        job_id = job_queue.enqueue(kind, payload or {"source": "cli"})
        while True:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None:
                    raise RuntimeError(f"Job {job_id} vanished")
                snapshot = {
                    "id": job.id,
                    "kind": job.kind,
                    "status": job.status,
                    "progress_pct": job.progress_pct,
                    "message": job.message,
                    "result_json": job.result_json,
                }
            if snapshot["status"] in ("succeeded", "failed"):
                return snapshot
            await asyncio.sleep(0.2)
    finally:
        await job_queue.stop()


def _update_job(job_id: str, **fields: Any) -> None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        for name, value in fields.items():
            setattr(job, name, value)


def next_version_no(session, asset_id: int) -> int:
    current = session.execute(
        select(func.max(AssetVersion.version_no)).where(AssetVersion.asset_id == asset_id)
    ).scalar_one()
    return (current or 0) + 1


def _persist_version(asset_id: int, generated: dict[str, Any], params: dict[str, Any]) -> int:
    version_id: int | None = None
    with session_scope() as session:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")
        version_no = next_version_no(session, asset_id)
        version = AssetVersion(
            asset_id=asset_id,
            version_no=version_no,
            prompt_snapshot=generated.get("prompt", ""),
            params_json=json.dumps(params, ensure_ascii=False),
            content_text=generated.get("content_text"),
            file_path=generated.get("file_path"),
            model_used=generated.get("model_used", ""),
            is_selected=version_no == 1,
        )
        session.add(version)
        session.flush()
        version_id = version.id
    _enqueue_brain_index(asset_version_id=version_id)
    return version_no


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_generate_asset(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .generation import generate_content

    asset_id = int(payload["asset_id"])
    asset_type = str(payload.get("type", "copy"))
    brief = str(payload.get("brief", ""))
    params = dict(payload.get("params") or {})

    _update_job(job_id, progress_pct=25, message=f"generating {asset_type}")
    generated = await generate_content(asset_type, brief, params)
    _update_job(job_id, progress_pct=80, message="persisting version")
    # brief/type ride along in params_json so /regenerate can replay the take.
    version_no = _persist_version(asset_id, generated, {"brief": brief, "type": asset_type, **params})
    return {"asset_id": asset_id, "version_no": version_no, "model_used": generated.get("model_used", "")}


async def _handle_run_daily_workflow(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if settings.local_only_agent_runs:
        from .local_workflow import run_local_daily_workflow

        _update_job(job_id, progress_pct=20, message="running deterministic local workflow")
        paths = await asyncio.to_thread(run_local_daily_workflow)
        _update_job(job_id, progress_pct=75, message="persisting workflow assets")
        assets = _persist_daily_output_assets(paths, mode="local_only", source=str(payload.get("source", "manual")))
        calendar_items = _persist_daily_calendar_items(assets, job_id=job_id)
        return {"mode": "local_only", "paths": paths, "assets": assets, "calendar_items": calendar_items}

    # TODO(fable-review): the full in-app agent pipeline lands in P3; until
    # then the live path reuses the legacy orchestrator entry point.
    _update_job(job_id, progress_pct=20, message="running legacy live workflow")
    from src.orchestrator import run_daily_workflow  # lazy: paid path, never hit in tests

    result = await asyncio.to_thread(asyncio.run, run_daily_workflow())
    return {"mode": "live", "result": str(result)}


def _persist_daily_output_assets(paths: dict[str, str], mode: str, source: str) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    version_ids: list[int] = []
    with session_scope() as session:
        for name, raw_path in paths.items():
            path = Path(raw_path)
            content_text = path.read_text(encoding="utf-8") if path.exists() else ""
            asset = session.execute(select(Asset).where(Asset.source_path == str(path))).scalar_one_or_none()
            if asset is None:
                asset = Asset(
                    type="copy",
                    title=f"Daily workflow: {name.replace('_', ' ').title()}",
                    status="draft",
                    source_path=str(path),
                )
                session.add(asset)
                session.flush()
                version = AssetVersion(
                    asset_id=asset.id,
                    version_no=1,
                    prompt_snapshot=f"run_daily_workflow:{name}",
                    params_json=json.dumps(
                        {"workflow": "run_daily_workflow", "mode": mode, "source": source, "output_key": name},
                        ensure_ascii=False,
                    ),
                    content_text=content_text,
                    file_path=str(path),
                    model_used=f"{mode}-daily-workflow",
                    is_selected=True,
                )
                session.add(version)
                session.flush()
                version_ids.append(version.id)
            persisted.append({"output_key": name, "asset_id": asset.id, "source_path": str(path)})
    for version_id in version_ids:
        _enqueue_brain_index(asset_version_id=version_id)
    return persisted


def _persist_daily_calendar_items(assets: list[dict[str, Any]], job_id: str) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    start_date = date.today()
    with session_scope() as session:
        for index, item in enumerate(assets):
            output_key = str(item.get("output_key", "output"))
            calendar_id = f"daily-workflow-{start_date.isoformat()}-{output_key}"
            row = session.get(CalendarItem, calendar_id)
            if row is None:
                row = CalendarItem(
                    id=calendar_id,
                    date=(start_date + timedelta(days=index)).isoformat(),
                    status="draft",
                    asset_id=int(item["asset_id"]) if item.get("asset_id") is not None else None,
                    data_json=json.dumps(
                        {
                            "title": f"Daily workflow: {output_key.replace('_', ' ').title()}",
                            "workflow_job_id": job_id,
                            "output_key": output_key,
                            "source_path": item.get("source_path", ""),
                        },
                        ensure_ascii=False,
                    ),
                )
                session.add(row)
            persisted.append({"id": row.id, "date": row.date, "asset_id": row.asset_id, "status": row.status})
    return persisted


async def _handle_render_carousel(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .rendering import render_text_carousel

    title = str(payload.get("title", "carousel"))
    slides = list(payload.get("slides") or [])
    _update_job(job_id, progress_pct=30, message="rendering slides")
    rendered = await asyncio.to_thread(render_text_carousel, title, slides)
    paths = [str(path) for path in rendered]

    asset_id = payload.get("asset_id")
    version_no = None
    if asset_id is not None:
        version_no = _persist_version(
            int(asset_id),
            {
                "prompt": f"render_text_carousel: {title}",
                "content_text": json.dumps({"slides": slides}, ensure_ascii=False),
                "file_path": paths[0] if paths else None,
                "model_used": "pillow-renderer",
            },
            {"slides": slides, "title": title},
        )
    return {"paths": paths, "asset_id": asset_id, "version_no": version_no}


async def _handle_image_iterate(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Live-only flow: images.generate_post_visual_image goes through the OpenAI
    # wrapper, which raises LocalOnlyModeError in local-only mode (the job is
    # then marked failed with that message — no silent fallback to paid calls).
    from .images import generate_post_visual_image

    item = dict(payload.get("item") or {})
    _update_job(job_id, progress_pct=30, message="iterating image")
    result = await asyncio.to_thread(
        generate_post_visual_image,
        item,
        str(payload.get("concept_type", "model_shoot")),
        str(payload.get("brief", "")),
        str(payload.get("direction", "")),
        [Path(p) for p in payload.get("reference_paths") or []],
    )
    asset_id = payload.get("asset_id")
    version_no = None
    if asset_id is not None:
        version_no = _persist_version(
            int(asset_id),
            {
                "prompt": result.get("prompt", ""),
                "content_text": None,
                "file_path": result.get("image_path"),
                "model_used": get_settings().image_model,
            },
            payload,
        )
    return {**{k: v for k, v in result.items() if k != "prompt"}, "asset_id": asset_id, "version_no": version_no}


async def _handle_brain_index(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .brain import handle_brain_index

    _update_job(job_id, progress_pct=30, message="indexing brand brain")
    return await handle_brain_index(payload)


async def _handle_distill_brand_profile(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .brand_profile import distill_brand_profile

    _update_job(job_id, progress_pct=30, message="distilling brand profile")
    return await distill_brand_profile()


async def _handle_seo_audit(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .seo_audit import audit_products, persist_audits
    from .seo_plan import latest_keyword_map
    from .shopify import ShopifyService

    _update_job(job_id, progress_pct=30, message="auditing Shopify catalog")
    preview = await asyncio.to_thread(ShopifyService().product_preview, int(payload.get("limit") or 80))
    products = [product for product in preview.get("products", []) if isinstance(product, dict)]
    with session_scope() as session:
        rows = persist_audits(session, audit_products(products, latest_keyword_map(session)))
        count = len(rows)
    return {"audits": count}


async def _handle_seo_fix(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .seo_fixes import generate_seo_fix

    audit_id = int(payload["audit_id"])
    asset_id = int(payload["asset_id"])
    _update_job(job_id, progress_pct=30, message="generating SEO fix")
    with session_scope() as session:
        generated = generate_seo_fix(session, audit_id)
        params = dict(generated.pop("params", {}))
    _update_job(job_id, progress_pct=80, message="persisting SEO fix")
    version_no = _persist_version(asset_id, generated, {"type": "seo_fix", **params})
    return {"asset_id": asset_id, "version_no": version_no}


async def _handle_seo_plan(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .seo_plan import generate_seo_plan

    asset_id = int(payload["asset_id"])
    _update_job(job_id, progress_pct=30, message="building SEO keyword plan")
    with session_scope() as session:
        generated = generate_seo_plan(session)
        params = dict(generated.pop("params", {}))
    _update_job(job_id, progress_pct=80, message="persisting SEO plan")
    version_no = _persist_version(asset_id, generated, {"type": "seo_plan", **params})
    return {"asset_id": asset_id, "version_no": version_no}


async def _handle_repurpose_shoot(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .generation import generate_content
    from .source_assets import resolve_reference_context

    source_asset_ids = [int(value) for value in payload.get("source_asset_ids") or []]
    if not 1 <= len(source_asset_ids) <= 10:
        raise ValueError("repurpose_shoot requires 1-10 source assets")
    brief = str(payload.get("brief") or "").strip()
    campaign_name = str(payload.get("campaign_name") or "").strip() or f"Repurposed shoot {date.today().isoformat()}"

    _update_job(job_id, progress_pct=10, message="creating repurpose campaign")
    with session_scope() as session:
        rows = session.execute(select(SourceAsset).where(SourceAsset.id.in_(source_asset_ids))).scalars().all()
        by_id = {row.id: row for row in rows}
        ordered = [by_id[source_id] for source_id in source_asset_ids if source_id in by_id]
        if len(ordered) != len(source_asset_ids):
            raise ValueError("One or more source assets were not found")
        campaign = Campaign(
            name=campaign_name,
            goal="Repurpose source shoot into copy, reel, story, ad, and product refresh drafts.",
            status="active",
        )
        session.add(campaign)
        session.flush()
        reference_context = resolve_reference_context(session, source_asset_ids[:4])
        source_summary = _source_summary(ordered)
        product_handle = next((row.product_handle for row in ordered if row.product_handle), "")
        specs = _repurpose_step_specs(campaign.id, brief, source_summary, source_asset_ids, reference_context, product_handle)
        for spec in specs:
            asset = Asset(campaign_id=campaign.id, type=spec["type"], title=spec["title"], status="draft")
            session.add(asset)
            session.flush()
            spec["asset_id"] = asset.id
        campaign_id = campaign.id

    steps: list[dict[str, Any]] = []
    total = len(specs)
    for index, spec in enumerate(specs, start=1):
        _update_job(job_id, progress_pct=10 + int((index - 1) / max(total, 1) * 75), message=f"running {spec['name']}")
        try:
            if spec["type"] == "seo_fix":
                generated = _repurpose_seo_fix(spec, product_handle)
                params = dict(spec["params"])
            else:
                params = dict(spec["params"])
                generated = await generate_content(str(spec["type"]), str(spec["brief"]), params)
            version_no = _persist_version(int(spec["asset_id"]), generated, {"type": spec["type"], "repurpose_step": spec["name"], **params})
            steps.append({"name": spec["name"], "status": "succeeded", "asset_id": spec["asset_id"], "version_no": version_no})
        except Exception as exc:
            logger.exception("repurpose_shoot step %s failed", spec["name"])
            steps.append({"name": spec["name"], "status": "failed", "asset_id": spec["asset_id"], "error": f"{type(exc).__name__}: {exc}"})
    _update_job(job_id, progress_pct=90, message="repurpose shoot complete")
    return {"campaign_id": campaign_id, "source_asset_ids": source_asset_ids, "steps": steps}


async def _handle_recycle_top_posts(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cutoff_days = int(payload.get("cutoff_days") or 45)
    cutoff = datetime.utcnow() - timedelta(days=cutoff_days)
    _update_job(job_id, progress_pct=30, message="selecting remix candidates")
    version_ids: list[int] = []
    with session_scope() as session:
        candidates = _top_quartile_remix_candidates(session, cutoff)
        created: list[dict[str, Any]] = []
        for post, metric in candidates:
            source_path = f"remix:{post.id}"
            existing = session.execute(select(Asset).where(Asset.source_path == source_path)).scalar_one_or_none()
            if existing is not None:
                continue
            title = (post.title_or_caption or post.permalink or post.external_ref or f"Post {post.id}")[:120]
            asset = Asset(type="copy", title=f"Remix: {title}", status="draft", source_path=source_path)
            session.add(asset)
            session.flush()
            version = AssetVersion(
                asset_id=asset.id,
                version_no=1,
                prompt_snapshot=f"recycle_top_posts:{post.id}",
                params_json=json.dumps(
                    {
                        "type": "copy",
                        "remix_of": post.id,
                        "source_post_channel": post.channel,
                        "engagement_rate": metric.engagement_rate,
                    },
                    ensure_ascii=False,
                ),
                content_text=_remix_content(post, metric),
                model_used="local-deterministic-recycle",
                is_selected=True,
            )
            session.add(version)
            session.flush()
            version_ids.append(version.id)
            created.append({"post_id": post.id, "asset_id": asset.id, "engagement_rate": metric.engagement_rate})
    for version_id in version_ids:
        _enqueue_brain_index(asset_version_id=version_id)
    return {"cutoff_days": cutoff_days, "candidates": len(candidates), "created": created}


def _enqueue_brain_index(**payload: Any) -> None:
    if not any(value is not None for value in payload.values()):
        return
    try:
        job_queue.enqueue("brain_index", payload)
    except Exception:
        logger.exception("Could not enqueue brain_index job")


def _source_summary(rows: list[SourceAsset]) -> str:
    lines = []
    for row in rows:
        try:
            tags = ", ".join(json.loads(row.tags_json or "[]")[:5])
        except (TypeError, json.JSONDecodeError):
            tags = ""
        handle = f" product={row.product_handle}" if row.product_handle else ""
        lines.append(f"- #{row.id} {row.origin}: {row.path}{handle}" + (f" tags={tags}" if tags else ""))
    return "\n".join(lines)


def _repurpose_step_specs(
    campaign_id: int,
    brief: str,
    source_summary: str,
    source_asset_ids: list[int],
    reference_context: dict[str, Any],
    product_handle: str,
) -> list[dict[str, Any]]:
    base_params = {
        **reference_context,
        "source_asset_ids_all": source_asset_ids,
        "repurpose_campaign_id": campaign_id,
    }
    base_brief = "\n".join(
        [
            brief or "Repurpose this shoot into review-ready growth drafts.",
            "",
            "Source assets:",
            source_summary,
        ]
    ).strip()
    specs: list[dict[str, Any]] = [
        {
            "name": "post_copy",
            "type": "copy",
            "title": "Repurpose: post copy",
            "brief": f"{base_brief}\n\nCreate one product-first social caption and CTA.",
            "params": {**base_params, "template": "repurpose_post_copy"},
        },
        {
            "name": "reel_video_script",
            "type": "video_script",
            "title": "Repurpose: reel video script",
            "brief": f"{base_brief}\n\nCreate a vertical reel prompt pack from the shoot.",
            "params": {**base_params, "template": "repurpose_reel"},
        },
        {
            "name": "story_set",
            "type": "copy",
            "title": "Repurpose: three-frame story set",
            "brief": f"{base_brief}\n\nCreate a three-frame story sequence: source, product proof, manual CTA.",
            "params": {**base_params, "template": "repurpose_story_set"},
        },
        {
            "name": "ad_brief",
            "type": "ad_brief",
            "title": "Repurpose: Meta ad brief",
            "brief": f"{base_brief}\n\nCreate a manual Meta ad brief grounded in this shoot.",
            "params": {
                **base_params,
                "objective": "Sales",
                "audience": "Warm streetwear audience and recent site visitors",
                "placement": "Instagram Feed + Reels",
                "hook": "Source work, now worn",
                "recommended_creative": "Use the strongest source asset from this repurpose shoot.",
            },
        },
    ]
    if product_handle:
        specs.append(
            {
                "name": "product_page_refresh",
                "type": "seo_fix",
                "title": f"Repurpose: SEO refresh for {product_handle}",
                "brief": base_brief,
                "params": {**base_params, "product_handle": product_handle},
            }
        )
    return specs


def _repurpose_seo_fix(spec: dict[str, Any], product_handle: str) -> dict[str, Any]:
    content = "\n".join(
        [
            f"# SEO Fix: {product_handle}",
            "",
            "## Product page refresh angle",
            "Use the strongest shoot proof as the source-of-truth story for this product page.",
            "",
            "## New title",
            f"{product_handle.replace('-', ' ').title()} - Source-Grounded Streetwear",
            "",
            "## Meta description",
            "Source-grounded streetwear with product proof from the latest shoot. Review details manually before updating Shopify.",
            "",
            "## Image alt text",
            f"{product_handle.replace('-', ' ')} product image grounded in the latest source shoot.",
            "",
            "## Manual use",
            "Copy these fields into Shopify manually after review. Shopify writes remain disabled.",
        ]
    )
    return {
        "prompt": str(spec.get("brief") or ""),
        "content_text": content,
        "file_path": None,
        "model_used": "local-deterministic",
    }


def _top_quartile_remix_candidates(session, cutoff: datetime) -> list[tuple[PublishedPost, PostMetric]]:
    posts = session.execute(
        select(PublishedPost).where(PublishedPost.published_at.is_not(None), PublishedPost.published_at <= cutoff)
    ).scalars().unique().all()
    scored: list[tuple[PublishedPost, PostMetric]] = []
    for post in posts:
        metric = _latest_metric_for_post(session, post.id)
        if metric is not None and metric.engagement_rate is not None:
            scored.append((post, metric))
    scored.sort(key=lambda item: (-(item[1].engagement_rate or 0), item[0].id))
    if not scored:
        return []
    keep = max(1, (len(scored) + 3) // 4)
    return scored[:keep]


def _latest_metric_for_post(session, post_id: int) -> PostMetric | None:
    return session.execute(
        select(PostMetric).where(PostMetric.published_post_id == post_id).order_by(PostMetric.captured_at.desc(), PostMetric.id.desc())
    ).scalars().first()


def _remix_content(post: PublishedPost, metric: PostMetric) -> str:
    percent = (metric.engagement_rate or 0) * 100
    title = post.title_or_caption or post.permalink or post.external_ref or f"Post {post.id}"
    return "\n".join(
        [
            f"# Remix Draft: {title}",
            "",
            f"Source post: {post.channel} #{post.id}",
            f"Latest engagement rate: {percent:.2f}%",
            "",
            "## Remix angle",
            "Rework the strongest hook and product proof into a fresh draft. Keep it unscheduled until reviewed.",
            "",
            "## Manual use",
            "Review, edit, and drag from the unscheduled tray when ready. No auto-scheduling was performed.",
        ]
    )


_HANDLERS = {
    "generate_asset": _handle_generate_asset,
    "run_daily_workflow": _handle_run_daily_workflow,
    "render_carousel": _handle_render_carousel,
    "image_iterate": _handle_image_iterate,
    "brain_index": _handle_brain_index,
    "distill_brand_profile": _handle_distill_brand_profile,
    "seo_audit": _handle_seo_audit,
    "seo_fix": _handle_seo_fix,
    "seo_plan": _handle_seo_plan,
    "repurpose_shoot": _handle_repurpose_shoot,
    "recycle_top_posts": _handle_recycle_top_posts,
}

# Application-wide queue instance (started/stopped by the FastAPI lifespan).
job_queue = JobQueue()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in JOB_KINDS:
        print(f"Usage: python -m app.services.jobs <{'|'.join(JOB_KINDS)}>", file=sys.stderr)
        return 2
    snapshot = asyncio.run(run_one_shot(args[0]))
    print(json.dumps(snapshot, ensure_ascii=False))
    return 0 if snapshot["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
