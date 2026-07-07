"""POST /api/v1/generate: create asset + enqueue generation job (P1-5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, Campaign
from ..schemas import GenerateRequest, GenerateResponse
from ..services.jobs import job_queue

router = APIRouter(tags=["playground"])


@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, session: Session = Depends(get_session)) -> GenerateResponse:
    if request.campaign_id is not None and session.get(Campaign, request.campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

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
            "params": request.params,
        },
    )
    return GenerateResponse(job_id=job_id, asset_id=asset.id)
