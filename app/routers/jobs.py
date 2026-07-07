"""Job status + SSE progress events (P1-5)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_session, session_scope
from ..models import Job
from ..schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

_POLL_INTERVAL = 0.15
_MAX_STREAM_SECONDS = 300


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _job_snapshot(job_id: str) -> dict | None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "progress_pct": job.progress_pct,
            "message": job.message,
            "result_json": job.result_json,
        }


@router.get("/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """SSE stream: progress/message events, then one completion event."""

    async def event_stream():
        elapsed = 0.0
        last_payload = None
        while elapsed < _MAX_STREAM_SECONDS:
            snapshot = _job_snapshot(job_id)
            if snapshot is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'Job not found'})}\n\n"
                return
            payload = json.dumps(snapshot, ensure_ascii=False)
            if snapshot["status"] in ("succeeded", "failed"):
                yield f"event: completion\ndata: {payload}\n\n"
                return
            if payload != last_payload:
                yield f"event: progress\ndata: {payload}\n\n"
                last_payload = payload
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
        yield f"event: error\ndata: {json.dumps({'detail': 'Stream timeout'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
