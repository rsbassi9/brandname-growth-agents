"""Library summary endpoints (P1-5). Asset browsing itself lives in assets.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Asset

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/summary")
def summary(session: Session = Depends(get_session)) -> dict:
    by_type = dict(
        session.execute(select(Asset.type, func.count()).group_by(Asset.type)).all()
    )
    by_status = dict(
        session.execute(select(Asset.status, func.count()).group_by(Asset.status)).all()
    )
    total = session.execute(select(func.count()).select_from(Asset)).scalar_one()
    return {"total": total, "by_type": by_type, "by_status": by_status}
