"""Ads workspace API for manual Meta Ads Manager brief prep."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, Campaign, SourceAsset
from ..schemas import AdBriefRequest, GenerateResponse
from ..services.jobs import job_queue
from ..services.source_assets import resolve_reference_context

router = APIRouter(prefix="/ads", tags=["ads"])


@router.post("/briefs", response_model=GenerateResponse)
def create_ad_brief(request: AdBriefRequest, session: Session = Depends(get_session)) -> GenerateResponse:
    if request.campaign_id is not None and session.get(Campaign, request.campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    linked_asset = session.get(Asset, request.asset_id) if request.asset_id is not None else None
    if request.asset_id is not None and linked_asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    source = session.get(SourceAsset, request.source_asset_id) if request.source_asset_id is not None else None
    if request.source_asset_id is not None and source is None:
        raise HTTPException(status_code=404, detail="Source asset not found")

    reference_context = resolve_reference_context(session, [source.id] if source is not None else [])
    creative = _recommended_creative(linked_asset, source)
    brief = request.brief.strip() or "\n".join(
        [
            f"Objective: {request.objective}",
            f"Audience: {request.audience}",
            f"Placement: {request.placement}",
            f"Hook: {request.hook}",
            f"Creative: {creative}",
        ]
    )

    asset = Asset(
        campaign_id=request.campaign_id,
        type="ad_brief",
        title=f"Meta ad brief: {request.hook[:100]}",
        status="draft",
    )
    session.add(asset)
    session.commit()

    params = {
        "template": "meta ad brief",
        "objective": request.objective,
        "audience": request.audience,
        "placement": request.placement,
        "hook": request.hook,
        "recommended_creative": creative,
        "linked_asset_id": linked_asset.id if linked_asset else None,
        "source_asset_id": source.id if source else None,
        "premium": request.premium,
        **reference_context,
    }
    job_id = job_queue.enqueue(
        "generate_asset",
        {"asset_id": asset.id, "type": "ad_brief", "brief": brief, "params": params},
    )
    return GenerateResponse(job_id=job_id, asset_id=asset.id)


def _recommended_creative(asset: Asset | None, source: SourceAsset | None) -> str:
    parts = []
    if asset is not None:
        parts.append(f"Library asset {asset.id}: {asset.title}")
    if source is not None:
        parts.append(f"Source photo {source.id}: {source.path}")
    return " + ".join(parts) if parts else "Select the strongest product/source image before launch."
