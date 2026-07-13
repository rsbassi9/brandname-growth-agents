"""SEO audit and fix API (P10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, SeoAudit
from ..schemas import GenerateResponse, SeoAuditOut, SeoAuditRunOut
from ..services.jobs import job_queue
from ..services.seo_audit import latest_audits

router = APIRouter(prefix="/seo", tags=["seo"])


@router.post("/audit", response_model=SeoAuditRunOut)
def run_seo_audit() -> SeoAuditRunOut:
    return SeoAuditRunOut(job_id=job_queue.enqueue("seo_audit", {"source": "manual"}))


@router.get("/audits", response_model=list[SeoAuditOut])
def seo_audits(
    session: Session = Depends(get_session),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SeoAuditOut]:
    return [SeoAuditOut.model_validate(row) for row in latest_audits(session, limit=limit)]


@router.post("/audits/{audit_id}/fix", response_model=GenerateResponse)
def generate_seo_fix(audit_id: int, session: Session = Depends(get_session)) -> GenerateResponse:
    audit = session.get(SeoAudit, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="SEO audit not found")
    asset = Asset(type="seo_fix", title=f"SEO fix: {audit.product_handle}", status="draft")
    session.add(asset)
    session.flush()
    session.commit()
    job_id = job_queue.enqueue("seo_fix", {"audit_id": audit.id, "asset_id": asset.id})
    return GenerateResponse(job_id=job_id, asset_id=asset.id)
