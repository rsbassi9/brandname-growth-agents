"""Strategy hub reads: brand context docs + feedback loop (P1-5).

brand_context/*.md is prompt/context IP: rendered read-only, never rewritten.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, AssetVersion, BrandProfileVersion, FeedbackEvent, StandupReport
from ..paths import brand_context_dir
from ..schemas import BrandProfileHistoryOut, FeedbackIn, FeedbackOut, StandupDraftOut, StandupReportOut, StrategyDocOut
from ..services.jobs import job_queue, next_version_no
from ..services.learning import FeedbackEntry, append_feedback, feedback_summary

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/context", response_model=list[StrategyDocOut])
def list_context_docs() -> list[StrategyDocOut]:
    directory = brand_context_dir()
    if not directory.exists():
        return []
    docs = []
    for path in sorted(directory.glob("*.md")):
        docs.append(StrategyDocOut(name=path.stem, content=path.read_text(encoding="utf-8")))
    return docs


@router.get("/context/{name}", response_model=StrategyDocOut)
def get_context_doc(name: str) -> StrategyDocOut:
    safe = "".join(char for char in name if char.isalnum() or char in ("-", "_"))
    path = brand_context_dir() / f"{safe}.md"
    if safe != name or not path.exists():
        raise HTTPException(status_code=404, detail="Context document not found")
    return StrategyDocOut(name=safe, content=path.read_text(encoding="utf-8"))


@router.get("/brand-profile", response_model=BrandProfileHistoryOut)
def brand_profile_history(session: Session = Depends(get_session)) -> BrandProfileHistoryOut:
    versions = session.execute(
        select(BrandProfileVersion).order_by(BrandProfileVersion.version_no.desc()).limit(20)
    ).scalars().all()
    return BrandProfileHistoryOut(current=versions[0] if versions else None, versions=versions)


@router.get("/standup", response_model=list[StandupReportOut])
def standup_reports(session: Session = Depends(get_session), limit: int = 10) -> list[StandupReport]:
    bounded_limit = min(max(limit, 1), 50)
    return session.execute(
        select(StandupReport).order_by(StandupReport.created_at.desc(), StandupReport.id.desc()).limit(bounded_limit)
    ).scalars().all()


@router.post("/standup/{report_id}/recommendations/{recommendation_index}/draft", response_model=StandupDraftOut)
def create_standup_recommendation_draft(
    report_id: int,
    recommendation_index: int,
    session: Session = Depends(get_session),
) -> StandupDraftOut:
    report = session.get(StandupReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Standup report not found")
    recommendations = _standup_recommendations(report)
    if recommendation_index < 0 or recommendation_index >= len(recommendations):
        raise HTTPException(status_code=404, detail="Standup recommendation not found")
    recommendation = recommendations[recommendation_index]
    source_path = f"standup:{report.id}:{recommendation_index}"
    existing = session.execute(select(Asset).where(Asset.source_path == source_path)).scalar_one_or_none()
    if existing is not None:
        return StandupDraftOut(asset_id=existing.id)
    asset = Asset(
        type=str(recommendation.get("draft_type") or "copy"),
        title=str(recommendation.get("title") or f"Standup recommendation {recommendation_index + 1}")[:255],
        status="draft",
        source_path=source_path,
    )
    session.add(asset)
    session.flush()
    version = AssetVersion(
        asset_id=asset.id,
        version_no=next_version_no(session, asset.id),
        prompt_snapshot=f"weekly_standup:{report.id}:{recommendation_index}",
        params_json=json.dumps(
            {
                "type": asset.type,
                "standup_report_id": report.id,
                "recommendation_index": recommendation_index,
                "evidence": recommendation.get("evidence") or {},
            },
            ensure_ascii=False,
        ),
        content_text=_standup_draft_content(report, recommendation, recommendation_index),
        model_used="local-deterministic-standup",
        is_selected=True,
    )
    session.add(version)
    session.commit()
    job_queue.enqueue("brain_index", {"asset_version_id": version.id})
    return StandupDraftOut(asset_id=asset.id)


@router.get("/learn/summary")
def learn_summary() -> dict:
    return {"summary": feedback_summary()}


@router.post("/learn/feedback", response_model=FeedbackOut, status_code=201)
def post_feedback(payload: FeedbackIn, session: Session = Depends(get_session)) -> FeedbackEvent:
    # Legacy jsonl store stays the learning source of truth; the DB row makes
    # feedback queryable through the API.
    stored = append_feedback(
        FeedbackEntry(
            output_path=payload.output_path,
            rating=payload.rating,
            comment=payload.comment,
            improvement_request=payload.improvement_request,
            category=payload.category,
        )
    )
    event = FeedbackEvent(
        id=stored["id"],
        created_at=stored["created_at"],
        output_path=stored["output_path"],
        rating=stored["rating"],
        comment=stored["comment"],
        improvement_request=stored["improvement_request"],
        category=stored["category"],
        data_json="{}",
    )
    session.add(event)
    session.commit()
    job_queue.enqueue("brain_index", {"feedback_id": event.id})
    return event


def _standup_recommendations(report: StandupReport) -> list[dict]:
    try:
        parsed = json.loads(report.recommendations_json or "[]")
    except json.JSONDecodeError:
        parsed = []
    return [item for item in parsed if isinstance(item, dict)]


def _standup_draft_content(report: StandupReport, recommendation: dict, index: int) -> str:
    return "\n".join(
        [
            f"# Draft from Weekly Standup Recommendation {index + 1}",
            "",
            f"Week start: {report.week_start}",
            f"Recommendation: {recommendation.get('title', '')}",
            "",
            "## Rationale",
            str(recommendation.get("rationale") or ""),
            "",
            "## Draft brief",
            str(recommendation.get("brief") or ""),
            "",
            "## Manual use",
            "Review, edit, and drag from the unscheduled tray when ready. No auto-scheduling was performed.",
        ]
    )
