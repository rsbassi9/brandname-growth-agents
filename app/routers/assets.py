"""Asset library API: list/detail/select/regenerate (P1-5)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, AssetVersion
from ..schemas import AssetDetailOut, AssetListOut, AssetOut, GenerateResponse
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
