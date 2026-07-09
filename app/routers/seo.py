"""SEO audit API (P10-1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import SeoAuditOut, SeoAuditRunOut
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
