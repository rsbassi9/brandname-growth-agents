"""System endpoints: health + mode (P1-5)."""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthOut, ModeOut
from ..settings import get_settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", brand=get_settings().brand_name)


@router.get("/mode", response_model=ModeOut)
def mode() -> ModeOut:
    settings = get_settings()
    return ModeOut(
        local_only_agent_runs=settings.local_only_agent_runs,
        brand_name=settings.brand_name,
        image_model=settings.image_model,
        model_default=settings.model_default,
        model_premium=settings.model_premium,
        openai_base_url=settings.openai_base_url,
    )
