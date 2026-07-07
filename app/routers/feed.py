"""Feed grid: ordered calendar items + persisted manual order (P1-5)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import CalendarItem, SettingsKV
from ..schemas import CalendarItemOut, FeedOrderIn

router = APIRouter(prefix="/feed", tags=["feed"])

_ORDER_KEY = "feed_order"


def _stored_order(session: Session) -> list[str]:
    row = session.get(SettingsKV, _ORDER_KEY)
    if row is None:
        return []
    try:
        value = json.loads(row.value or "[]")
    except json.JSONDecodeError:
        # Explicit fallback: a corrupt stored order degrades to date order.
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


@router.get("", response_model=list[CalendarItemOut])
def feed(session: Session = Depends(get_session)) -> list[CalendarItemOut]:
    items = session.execute(
        select(CalendarItem).order_by(CalendarItem.date.desc(), CalendarItem.id)
    ).scalars().all()
    order = _stored_order(session)
    rank = {item_id: index for index, item_id in enumerate(order)}
    items.sort(key=lambda item: (rank.get(item.id, len(rank)),))
    return [
        CalendarItemOut(
            id=item.id,
            date=item.date,
            status=item.status,
            asset_id=item.asset_id,
            data=json.loads(item.data_json or "{}"),
        )
        for item in items
    ]


@router.post("/order")
def set_order(payload: FeedOrderIn, session: Session = Depends(get_session)) -> dict:
    row = session.get(SettingsKV, _ORDER_KEY)
    value = json.dumps(payload.item_ids, ensure_ascii=False)
    if row is None:
        session.add(SettingsKV(key=_ORDER_KEY, value=value))
    else:
        row.value = value
    session.commit()
    return {"ok": True, "count": len(payload.item_ids)}
