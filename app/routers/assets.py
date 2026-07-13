"""Asset library API: list/detail/select/regenerate (P1-5)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, AssetVersion
from ..paths import ROOT_DIR, data_root, outputs_dir
from ..schemas import AssetDetailOut, AssetListOut, AssetOut, CritiqueOut, GenerateResponse
from ..services.jobs import job_queue

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=AssetListOut)
def list_assets(
    session: Session = Depends(get_session),
    type: str | None = None,
    campaign_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AssetListOut:
    query = select(Asset)
    if type:
        query = query.where(Asset.type == type)
    if campaign_id is not None:
        query = query.where(Asset.campaign_id == campaign_id)
    if status:
        query = query.where(Asset.status == status)
    if q:
        query = query.where(Asset.title.ilike(f"%{q}%"))
    if date_from:
        query = query.where(Asset.created_at >= date_from)
    if date_to:
        query = query.where(Asset.created_at <= f"{date_to} 23:59:59")

    total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = session.execute(
        query.order_by(Asset.created_at.desc(), Asset.id.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return AssetListOut(
        items=[AssetOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{asset_id}", response_model=AssetDetailOut)
def get_asset(asset_id: int, session: Session = Depends(get_session)) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/media")
def get_asset_media(asset_id: int, session: Session = Depends(get_session)) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    version = session.execute(
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id, AssetVersion.file_path.is_not(None))
        .order_by(AssetVersion.is_selected.desc(), AssetVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    if version is None or not version.file_path:
        raise HTTPException(status_code=404, detail="Asset has no media file")
    path = _resolve_media_path(version.file_path)
    if path is None or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(status_code=415, detail="Asset media is not a supported image")
    return FileResponse(path)


@router.post("/{asset_id}/versions/{version_no}/select", response_model=AssetDetailOut)
def select_version(asset_id: int, version_no: int, session: Session = Depends(get_session)) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    versions = session.execute(
        select(AssetVersion).where(AssetVersion.asset_id == asset_id)
    ).scalars().all()
    target = next((version for version in versions if version.version_no == version_no), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")
    # Only the is_selected flag may change: version content stays immutable.
    for version in versions:
        version.is_selected = version.id == target.id
    asset.status = "selected"
    session.commit()
    return asset


@router.post("/{asset_id}/versions/{version_no}/critique", response_model=CritiqueOut)
def critique_version(asset_id: int, version_no: int, session: Session = Depends(get_session)) -> CritiqueOut:
    asset, version = _asset_and_version(session, asset_id, version_no)
    stored = json.loads(version.params_json or "{}")
    critique = stored.get("critique") or _build_critique(asset, version)
    stored["critique"] = critique
    version.params_json = json.dumps(stored, ensure_ascii=False)
    session.commit()
    return CritiqueOut(asset_id=asset.id, version_no=version.version_no, critique=critique)


@router.post("/{asset_id}/versions/{version_no}/iterate", response_model=GenerateResponse)
def iterate_version(asset_id: int, version_no: int, session: Session = Depends(get_session)) -> GenerateResponse:
    asset, version = _asset_and_version(session, asset_id, version_no)
    stored = json.loads(version.params_json or "{}")
    critique = stored.get("critique") or _build_critique(asset, version)
    stored["critique"] = critique
    version.params_json = json.dumps(stored, ensure_ascii=False)
    brief = str(stored.get("brief") or version.content_text or asset.title)
    params = {k: v for k, v in stored.items() if k not in {"type"}}
    params["iteration_of"] = version.version_no
    params["critique"] = critique
    session.commit()
    job_id = job_queue.enqueue(
        "generate_asset",
        {"asset_id": asset.id, "type": asset.type, "brief": brief, "params": params},
    )
    return GenerateResponse(job_id=job_id, asset_id=asset.id)


@router.post("/{asset_id}/regenerate", response_model=GenerateResponse)
def regenerate(asset_id: int, session: Session = Depends(get_session)) -> GenerateResponse:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    latest = session.execute(
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id)
        .order_by(AssetVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        raise HTTPException(status_code=409, detail="Asset has no version to regenerate from")

    stored = json.loads(latest.params_json or "{}")
    brief = str(stored.pop("brief", ""))
    stored.pop("type", None)
    job_id = job_queue.enqueue(
        "generate_asset",
        {"asset_id": asset_id, "type": asset.type, "brief": brief, "params": stored},
    )
    return GenerateResponse(job_id=job_id, asset_id=asset_id)


@router.post("/{asset_id}/video-prompt-pack", response_model=GenerateResponse)
def create_video_prompt_pack(asset_id: int, session: Session = Depends(get_session)) -> GenerateResponse:
    source = session.get(Asset, asset_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    latest = session.execute(
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id)
        .order_by(AssetVersion.is_selected.desc(), AssetVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    source_text = latest.content_text if latest and latest.content_text else source.title
    video_asset = Asset(
        campaign_id=source.campaign_id,
        type="video_script",
        title=f"Video prompt pack: {source.title[:180]}",
        status="draft",
    )
    session.add(video_asset)
    session.commit()
    job_id = job_queue.enqueue(
        "generate_asset",
        {
            "asset_id": video_asset.id,
            "type": "video_script",
            "brief": f"Create an external video prompt pack from this asset:\n\n{source_text}",
            "params": {
                "template": "video prompt pack",
                "source_asset_id": source.id,
                "source_note": f"Ground this pack in Library asset {source.id}: {source.title}",
            },
        },
    )
    return GenerateResponse(job_id=job_id, asset_id=video_asset.id)


def _resolve_media_path(raw_path: str) -> Path | None:
    candidates: list[Path] = []
    raw = Path(raw_path)
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend([data_root() / raw_path, ROOT_DIR / raw_path])
        if raw_path.startswith("outputs/"):
            candidates.append(outputs_dir() / raw_path.removeprefix("outputs/"))
    allowed_roots = [ROOT_DIR.resolve(), data_root().resolve()]
    resolved_candidates: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if any(resolved == root or root in resolved.parents for root in allowed_roots):
            resolved_candidates.append(resolved)
    for resolved in resolved_candidates:
        if resolved.exists():
            return resolved
    if resolved_candidates:
        return resolved_candidates[0]
    return None


def _asset_and_version(session: Session, asset_id: int, version_no: int) -> tuple[Asset, AssetVersion]:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    version = session.execute(
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id, AssetVersion.version_no == version_no)
        .limit(1)
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return asset, version


def _build_critique(asset: Asset, version: AssetVersion) -> str:
    content = (version.content_text or version.file_path or asset.title or "").strip()
    sample = content[:280] if content else asset.title
    return "\n".join(
        [
            f"QA critique for {asset.type} v{version.version_no}:",
            "- Keep the concept grounded in the approved source imagery and product truth.",
            "- Make the first line or frame more specific to the garment, source painting, or reconstruction detail.",
            "- Remove any generic fashion phrasing; preserve the quiet, premium system language.",
            "- Next iteration should sharpen one concrete visual detail and one manual publishing cue.",
            "",
            f"Version evidence: {sample}",
        ]
    )
