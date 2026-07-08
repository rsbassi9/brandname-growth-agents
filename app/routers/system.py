"""System endpoints: health + mode (P1-5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import DailyWorkflowRunOut, DailyWorkflowScheduleIn, DailyWorkflowScheduleOut, HealthOut, ModeOut
from ..services.scheduler import enqueue_daily_workflow, get_daily_workflow_schedule, set_daily_workflow_schedule
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


@router.get("/daily-workflow", response_model=DailyWorkflowScheduleOut)
def daily_workflow_schedule() -> DailyWorkflowScheduleOut:
    schedule = get_daily_workflow_schedule()
    return DailyWorkflowScheduleOut(
        enabled=schedule.enabled,
        time_local=schedule.time_local,
        last_enqueued_date=schedule.last_enqueued_date,
    )


@router.put("/daily-workflow", response_model=DailyWorkflowScheduleOut)
def update_daily_workflow_schedule(payload: DailyWorkflowScheduleIn) -> DailyWorkflowScheduleOut:
    try:
        schedule = set_daily_workflow_schedule(payload.enabled, payload.time_local)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DailyWorkflowScheduleOut(
        enabled=schedule.enabled,
        time_local=schedule.time_local,
        last_enqueued_date=schedule.last_enqueued_date,
    )


@router.post("/daily-workflow/run", response_model=DailyWorkflowRunOut)
def run_daily_workflow_now() -> DailyWorkflowRunOut:
    return DailyWorkflowRunOut(job_id=enqueue_daily_workflow("manual"))
