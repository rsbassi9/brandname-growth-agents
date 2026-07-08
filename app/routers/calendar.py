"""Calendar CRUD against the calendar_items table (P1-5).

Behavior ported from the legacy dashboard's calendar handlers; all reads and
writes now go through the DB (data_json keeps every legacy field).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset, CalendarItem
from ..schemas import CalendarItemIn, CalendarItemOut, CalendarItemPatch, GenerateResponse
from ..services.jobs import job_queue

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _to_out(item: CalendarItem) -> CalendarItemOut:
    return CalendarItemOut(
        id=item.id,
        date=item.date,
        status=item.status,
        asset_id=item.asset_id,
        data=json.loads(item.data_json or "{}"),
    )


@router.get("", response_model=list[CalendarItemOut])
def list_items(
    session: Session = Depends(get_session),
    month: str | None = None,
    date: str | None = None,
    status: str | None = None,
) -> list[CalendarItemOut]:
    query = select(CalendarItem)
    if month:
        query = query.where(CalendarItem.date.like(f"{month}%"))
    if date:
        query = query.where(CalendarItem.date == date)
    if status:
        query = query.where(CalendarItem.status == status)
    rows = session.execute(query.order_by(CalendarItem.date, CalendarItem.id)).scalars().all()
    return [_to_out(row) for row in rows]


@router.post("", response_model=CalendarItemOut, status_code=201)
def create_item(payload: CalendarItemIn, session: Session = Depends(get_session)) -> CalendarItemOut:
    item_id = payload.id or f"post-{uuid.uuid4().hex[:12]}"
    if session.get(CalendarItem, item_id) is not None:
        raise HTTPException(status_code=409, detail="Calendar item id already exists")
    data = dict(payload.data)
    data.setdefault("id", item_id)
    item = CalendarItem(
        id=item_id,
        date=payload.date,
        status=payload.status,
        asset_id=payload.asset_id,
        data_json=json.dumps(data, ensure_ascii=False),
    )
    session.add(item)
    session.commit()
    return _to_out(item)


@router.get("/{item_id}", response_model=CalendarItemOut)
def get_item(item_id: str, session: Session = Depends(get_session)) -> CalendarItemOut:
    item = session.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    return _to_out(item)


@router.patch("/{item_id}", response_model=CalendarItemOut)
def patch_item(item_id: str, payload: CalendarItemPatch, session: Session = Depends(get_session)) -> CalendarItemOut:
    item = session.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    if payload.date is not None:
        item.date = payload.date
    if payload.status is not None:
        item.status = payload.status
    if payload.asset_id is not None:
        item.asset_id = payload.asset_id
    if payload.data is not None:
        merged = json.loads(item.data_json or "{}")
        merged.update(payload.data)
        item.data_json = json.dumps(merged, ensure_ascii=False)
    session.commit()
    return _to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: str, session: Session = Depends(get_session)) -> None:
    item = session.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    session.delete(item)
    session.commit()


@router.post("/{item_id}/video-prompt-pack", response_model=GenerateResponse)
def create_video_prompt_pack(item_id: str, session: Session = Depends(get_session)) -> GenerateResponse:
    item = session.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    data = json.loads(item.data_json or "{}")
    linked_asset = session.get(Asset, item.asset_id) if item.asset_id is not None else None
    fallback_title = linked_asset.title if linked_asset else item_id
    title = str(data.get("title") or data.get("hook") or fallback_title)
    brief = "\n".join(
        [
            f"Create an external video prompt pack for calendar item {item.id}.",
            f"Date: {item.date}",
            f"Status: {item.status}",
            f"Title: {title}",
            f"Linked asset: {linked_asset.title if linked_asset else 'none'}",
            f"Calendar data: {json.dumps(data, ensure_ascii=False)}",
        ]
    )
    video_asset = Asset(
        campaign_id=linked_asset.campaign_id if linked_asset else None,
        type="video_script",
        title=f"Video prompt pack: {title[:180]}",
        status="draft",
    )
    session.add(video_asset)
    session.commit()
    job_id = job_queue.enqueue(
        "generate_asset",
        {
            "asset_id": video_asset.id,
            "type": "video_script",
            "brief": brief,
            "params": {
                "template": "video prompt pack",
                "source_calendar_item_id": item.id,
                "source_asset_id": linked_asset.id if linked_asset else None,
                "source_note": f"Ground this pack in calendar item {item.id} and its linked asset/source notes.",
            },
        },
    )
    return GenerateResponse(job_id=job_id, asset_id=video_asset.id)
