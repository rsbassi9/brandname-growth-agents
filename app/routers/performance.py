"""Performance import API (P8-2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import PublishedPost
from ..schemas import (
    BestTimeSlotOut,
    PerformanceAssetTypeOut,
    PerformanceDashboardOut,
    PerformanceImportOut,
    PerformanceTopPostOut,
    PerformanceTrendOut,
    PostMetricOut,
    PublishedPostLinkIn,
    PublishedPostListOut,
    PublishedPostOut,
)
from ..services.performance import (
    PerformanceImportError,
    best_times,
    import_performance_csv,
    link_published_post,
    parse_import_request_body,
    performance_dashboard,
    unlink_published_post,
)

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/best-times", response_model=list[BestTimeSlotOut])
def performance_best_times(
    session: Session = Depends(get_session),
    channel: str | None = None,
) -> list[BestTimeSlotOut]:
    return [BestTimeSlotOut(**slot.__dict__) for slot in best_times(session, channel=channel)]


@router.get("/dashboard", response_model=PerformanceDashboardOut)
def performance_dashboard_summary(session: Session = Depends(get_session)) -> PerformanceDashboardOut:
    dashboard = performance_dashboard(session)
    return PerformanceDashboardOut(
        top_posts=[PerformanceTopPostOut(**item.__dict__) for item in dashboard.top_posts],
        weekly_trend=[PerformanceTrendOut(**item.__dict__) for item in dashboard.weekly_trend],
        by_asset_type=[PerformanceAssetTypeOut(**item.__dict__) for item in dashboard.by_asset_type],
    )


@router.get("/posts", response_model=PublishedPostListOut)
def list_published_posts(
    session: Session = Depends(get_session),
    channel: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PublishedPostListOut:
    query = select(PublishedPost)
    count_query = select(func.count()).select_from(PublishedPost)
    if channel:
        query = query.where(PublishedPost.channel == channel)
        count_query = count_query.where(PublishedPost.channel == channel)
    rows = session.execute(
        query.order_by(PublishedPost.published_at.desc().nullslast(), PublishedPost.id.desc()).limit(limit).offset(offset)
    ).scalars().all()
    total = session.execute(count_query).scalar_one()
    return PublishedPostListOut(items=[PublishedPostOut.model_validate(row) for row in rows], total=total)


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


@router.patch("/posts/{post_id}/link", response_model=PublishedPostOut)
def link_post(post_id: int, payload: PublishedPostLinkIn, session: Session = Depends(get_session)) -> PublishedPostOut:
    try:
        post = link_published_post(session, post_id, payload.calendar_item_id, payload.asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return PublishedPostOut.model_validate(post)


@router.delete("/posts/{post_id}/link", response_model=PublishedPostOut)
def unlink_post(post_id: int, session: Session = Depends(get_session)) -> PublishedPostOut:
    try:
        post = unlink_published_post(session, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return PublishedPostOut.model_validate(post)
