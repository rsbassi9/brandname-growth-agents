"""Performance import API (P8-2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import PerformanceImportOut, PostMetricOut, PublishedPostOut
from ..services.performance import PerformanceImportError, import_performance_csv, parse_import_request_body

router = APIRouter(prefix="/performance", tags=["performance"])


@router.post("/import", response_model=PerformanceImportOut)
async def import_performance(request: Request, session: Session = Depends(get_session)) -> PerformanceImportOut:
    try:
        channel, csv_text = parse_import_request_body(request.headers.get("content-type", ""), await request.body())
        result = import_performance_csv(session, channel, csv_text)
    except PerformanceImportError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "detected_columns": exc.detected_columns}) from exc
    session.commit()
    return PerformanceImportOut(
        status=result.status,
        detected_columns=result.detected_columns,
        posts_upserted=result.posts_upserted,
        metrics_inserted=result.metrics_inserted,
        warnings=result.warnings,
        posts=[PublishedPostOut.model_validate(post) for post in result.posts],
        metrics=[PostMetricOut.model_validate(metric) for metric in result.metrics],
    )
