"""Source photo library API for P4-4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import SourceAssetIndexRequest, SourceAssetListOut, SourceAssetOut
from ..services.source_assets import (
    index_drive_sources,
    index_local_folder,
    index_shopify_sources,
    list_source_assets,
)

router = APIRouter(prefix="/source-assets", tags=["source-assets"])


@router.get("", response_model=SourceAssetListOut)
def list_sources(
    session: Session = Depends(get_session),
    origin: str | None = None,
    q: str | None = None,
) -> SourceAssetListOut:
    rows, total = list_source_assets(session, origin=origin, q=q)
    return SourceAssetListOut(items=[SourceAssetOut.model_validate(row) for row in rows], total=total)


@router.post("/index", response_model=SourceAssetListOut)
def index_sources(request: SourceAssetIndexRequest, session: Session = Depends(get_session)) -> SourceAssetListOut:
    try:
        if request.origin == "local":
            rows = index_local_folder(session, request.path, request.tags, request.limit)
        elif request.origin == "drive":
            rows = index_drive_sources(session, request.tags, request.limit)
        elif request.origin == "shopify":
            rows = index_shopify_sources(session, request.tags, request.limit)
        else:
            raise HTTPException(status_code=400, detail="Unsupported source asset origin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return SourceAssetListOut(items=[SourceAssetOut.model_validate(row) for row in rows], total=len(rows))
