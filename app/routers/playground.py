"""POST /api/v1/generate: create asset + enqueue generation job (P1-5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, Campaign
from ..schemas import GenerateRequest, GenerateResponse
from ..services.jobs import job_queue
from ..services.source_assets import resolve_reference_context

router = APIRouter(tags=["playground"])


@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, session: Session = Depends(get_session)) -> GenerateResponse:
    if request.campaign_id is not None and session.get(Campaign, request.campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    params = dict(request.params)
    source_asset_ids = params.get("source_asset_ids") or []
    if not isinstance(source_asset_ids, list):
        raise HTTPException(status_code=422, detail="source_asset_ids must be a list")
    if len(source_asset_ids) > 4:
        raise HTTPException(status_code=422, detail="Attach between 1 and 4 source assets")
    try:
        requested_source_ids = [int(value) for value in source_asset_ids]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="source_asset_ids must contain integer ids") from exc
    reference_context = resolve_reference_context(session, requested_source_ids)
    if source_asset_ids and len(reference_context["source_asset_ids"]) != len(source_asset_ids):
        raise HTTPException(status_code=404, detail="One or more source assets were not found")
    params.update(reference_context)

    asset = Asset(
        campaign_id=request.campaign_id,
        type=request.type,
        title=request.title or request.brief.strip().splitlines()[0][:120],
        status="draft",
    )
    session.add(asset)
    # Commit before enqueueing: the job worker writes from its own connection
    # and must not contend with this request's SQLite write lock.
    session.commit()

    job_id = job_queue.enqueue(
        "generate_asset",
        {
            "asset_id": asset.id,
            "type": request.type,
            "brief": request.brief,
            "params": params,
        },
    )
    return GenerateResponse(job_id=job_id, asset_id=asset.id)
