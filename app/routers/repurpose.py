"""Repurposing pipeline API (P11-1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, SourceAsset
from ..schemas import GenerateResponse, RepurposeShootRequest, RepurposeShootRunOut
from ..services.jobs import job_queue

router = APIRouter(prefix="/repurpose", tags=["repurpose"])


@router.post("/shoot", response_model=RepurposeShootRunOut)
def repurpose_shoot(request: RepurposeShootRequest, session: Session = Depends(get_session)) -> RepurposeShootRunOut:
    ids = [int(value) for value in request.source_asset_ids]
    rows = session.execute(select(SourceAsset.id).where(SourceAsset.id.in_(ids))).scalars().all()
    if set(rows) != set(ids):
        raise HTTPException(status_code=404, detail="One or more source assets were not found")
    job_id = job_queue.enqueue(
        "repurpose_shoot",
        {"source_asset_ids": ids, "campaign_name": request.campaign_name, "brief": request.brief},
    )
    return RepurposeShootRunOut(job_id=job_id)


@router.post("/assets/{asset_id}/retry", response_model=GenerateResponse)
def retry_repurpose_asset(asset_id: int, session: Session = Depends(get_session)) -> GenerateResponse:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not asset.source_path or not asset.source_path.startswith("repurpose:"):
        raise HTTPException(status_code=409, detail="Asset is not a repurpose step")
    job_id = job_queue.enqueue(
        "generate_asset",
        {
            "asset_id": asset.id,
            "type": asset.type,
            "brief": f"Retry repurpose step: {asset.title}",
            "params": {"repurpose_retry": True, "repurpose_source_path": asset.source_path},
        },
    )
    return GenerateResponse(job_id=job_id, asset_id=asset.id)
