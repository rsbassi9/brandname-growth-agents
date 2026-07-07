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
from ..models import CalendarItem
from ..schemas import CalendarItemIn, CalendarItemOut, CalendarItemPatch

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
