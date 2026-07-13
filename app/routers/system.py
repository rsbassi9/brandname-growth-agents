"""System endpoints: health + mode (P1-5)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Job, SettingsKV
from ..schemas import (
    BrandProfileDistillationScheduleIn,
    BrandProfileDistillationScheduleOut,
    CalendarGuardrailsIn,
    CalendarGuardrailsOut,
    DailyWorkflowRunOut,
    DailyWorkflowScheduleIn,
    DailyWorkflowScheduleOut,
    HealthOut,
    ModeOut,
    RecyclingScheduleIn,
    RecyclingScheduleOut,
    WorkflowRunReportOut,
    WorkflowRunStepOut,
)
from ..services.scheduler import (
    enqueue_brand_profile_distillation,
    enqueue_daily_workflow,
    enqueue_recycling,
    get_brand_profile_distillation_schedule,
    get_daily_workflow_schedule,
    get_recycling_schedule,
    set_brand_profile_distillation_schedule,
    set_daily_workflow_schedule,
    set_recycling_schedule,
)
from ..settings import get_settings

router = APIRouter(prefix="/system", tags=["system"])
_CALENDAR_GUARDRAILS_KEY = "calendar_guardrails.max_items_per_day_channel"


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


@router.get("/brand-profile-distillation", response_model=BrandProfileDistillationScheduleOut)
def brand_profile_distillation_schedule() -> BrandProfileDistillationScheduleOut:
    schedule = get_brand_profile_distillation_schedule()
    return BrandProfileDistillationScheduleOut(
        enabled=schedule.enabled,
        time_local=schedule.time_local,
        weekday=schedule.weekday,
        last_enqueued_date=schedule.last_enqueued_date,
    )


@router.put("/brand-profile-distillation", response_model=BrandProfileDistillationScheduleOut)
def update_brand_profile_distillation_schedule(
    payload: BrandProfileDistillationScheduleIn,
) -> BrandProfileDistillationScheduleOut:
    try:
        schedule = set_brand_profile_distillation_schedule(payload.enabled, payload.time_local, payload.weekday)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BrandProfileDistillationScheduleOut(
        enabled=schedule.enabled,
        time_local=schedule.time_local,
        weekday=schedule.weekday,
        last_enqueued_date=schedule.last_enqueued_date,
    )


@router.get("/calendar-guardrails", response_model=CalendarGuardrailsOut)
def calendar_guardrails(session: Session = Depends(get_session)) -> CalendarGuardrailsOut:
    return CalendarGuardrailsOut(max_items_per_day_channel=_calendar_guardrail_limit(session))


@router.put("/calendar-guardrails", response_model=CalendarGuardrailsOut)
def update_calendar_guardrails(
    payload: CalendarGuardrailsIn,
    session: Session = Depends(get_session),
) -> CalendarGuardrailsOut:
    row = session.get(SettingsKV, _CALENDAR_GUARDRAILS_KEY)
    if row is None:
        session.add(SettingsKV(key=_CALENDAR_GUARDRAILS_KEY, value=str(payload.max_items_per_day_channel)))
    else:
        row.value = str(payload.max_items_per_day_channel)
    session.commit()
    return CalendarGuardrailsOut(max_items_per_day_channel=payload.max_items_per_day_channel)


@router.post("/brand-profile-distillation/run", response_model=DailyWorkflowRunOut)
def run_brand_profile_distillation_now() -> DailyWorkflowRunOut:
    return DailyWorkflowRunOut(job_id=enqueue_brand_profile_distillation("manual"))


@router.get("/recycling", response_model=RecyclingScheduleOut)
def recycling_schedule() -> RecyclingScheduleOut:
    schedule = get_recycling_schedule()
    return RecyclingScheduleOut(
        enabled=schedule.enabled,
        day=schedule.day,
        time_local=schedule.time_local,
        last_enqueued_month=schedule.last_enqueued_month,
    )


@router.put("/recycling", response_model=RecyclingScheduleOut)
def update_recycling_schedule(payload: RecyclingScheduleIn) -> RecyclingScheduleOut:
    try:
        schedule = set_recycling_schedule(payload.enabled, payload.day, payload.time_local)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RecyclingScheduleOut(
        enabled=schedule.enabled,
        day=schedule.day,
        time_local=schedule.time_local,
        last_enqueued_month=schedule.last_enqueued_month,
    )


@router.post("/recycling/run", response_model=DailyWorkflowRunOut)
def run_recycling_now() -> DailyWorkflowRunOut:
    return DailyWorkflowRunOut(job_id=enqueue_recycling("manual"))


@router.get("/daily-workflow/runs", response_model=list[WorkflowRunReportOut])
def daily_workflow_runs(
    session: Session = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[WorkflowRunReportOut]:
    rows = session.execute(
        select(Job)
        .where(Job.kind == "run_daily_workflow")
        .order_by(Job.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [_workflow_run_out(row) for row in rows]


def _workflow_run_out(job: Job) -> WorkflowRunReportOut:
    result = _load_result(job.result_json)
    steps: list[WorkflowRunStepOut] = []
    for item in result.get("assets") or []:
        name = str(item.get("output_key", "output"))
        asset_id = item.get("asset_id")
        steps.append(
            WorkflowRunStepOut(
                name=name,
                status="asset_created" if asset_id else "output_written",
                asset_id=int(asset_id) if asset_id is not None else None,
                source_path=str(item.get("source_path", "")),
            )
        )
    if not steps:
        for name, source_path in (result.get("paths") or {}).items():
            steps.append(
                WorkflowRunStepOut(
                    name=str(name),
                    status="output_written" if job.status == "succeeded" else job.status,
                    source_path=str(source_path),
                )
            )
    return WorkflowRunReportOut(
        id=job.id,
        status=job.status,
        progress_pct=job.progress_pct,
        message=job.message,
        mode=str(result.get("mode", "")),
        created_at=job.created_at,
        finished_at=job.finished_at,
        steps=steps,
    )


def _load_result(result_json: str | None) -> dict:
    if not result_json:
        return {}
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        return {}
    return result if isinstance(result, dict) else {}


def _calendar_guardrail_limit(session: Session) -> int:
    row = session.get(SettingsKV, _CALENDAR_GUARDRAILS_KEY)
    if row is None:
        return 3
    try:
        value = int(row.value)
    except ValueError:
        return 3
    return min(max(value, 1), 20)
