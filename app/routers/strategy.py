"""Strategy hub reads: brand context docs + feedback loop (P1-5).

brand_context/*.md is prompt/context IP: rendered read-only, never rewritten.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import FeedbackEvent
from ..paths import brand_context_dir
from ..schemas import FeedbackIn, FeedbackOut, StrategyDocOut
from ..services.jobs import job_queue
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
