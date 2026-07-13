"""In-app daily workflow scheduler (P3-1).

The scheduler is intentionally small and dependency-free: it mirrors the
existing in-process job worker and reads `settings_kv` so it can be controlled
from the app without environment changes. It is off by default.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime

from ..db import session_scope
from ..models import SettingsKV
from .jobs import job_queue

logger = logging.getLogger(__name__)

_ENABLED_KEY = "daily_workflow.enabled"
_TIME_KEY = "daily_workflow.time_local"
_LAST_DATE_KEY = "daily_workflow.last_enqueued_date"
_PROFILE_ENABLED_KEY = "brand_profile_distillation.enabled"
_PROFILE_TIME_KEY = "brand_profile_distillation.time_local"
_PROFILE_WEEKDAY_KEY = "brand_profile_distillation.weekday"
_PROFILE_LAST_DATE_KEY = "brand_profile_distillation.last_enqueued_date"
_RECYCLE_ENABLED_KEY = "recycling.enabled"
_RECYCLE_DAY_KEY = "recycling.day"
_RECYCLE_TIME_KEY = "recycling.time_local"
_RECYCLE_LAST_MONTH_KEY = "recycling.last_enqueued_month"
_STANDUP_ENABLED_KEY = "weekly_standup.enabled"
_STANDUP_TIME_KEY = "weekly_standup.time_local"
_STANDUP_WEEKDAY_KEY = "weekly_standup.weekday"
_STANDUP_LAST_DATE_KEY = "weekly_standup.last_enqueued_date"
_DEFAULT_TIME = "09:00"
_POLL_SECONDS = 30


@dataclass(frozen=True)
class DailyWorkflowSchedule:
    enabled: bool
    time_local: str
    last_enqueued_date: str


@dataclass(frozen=True)
class BrandProfileDistillationSchedule:
    enabled: bool
    time_local: str
    weekday: int
    last_enqueued_date: str


@dataclass(frozen=True)
class RecyclingSchedule:
    enabled: bool
    day: int
    time_local: str
    last_enqueued_month: str


@dataclass(frozen=True)
class WeeklyStandupSchedule:
    enabled: bool
    time_local: str
    weekday: int
    last_enqueued_date: str


def get_daily_workflow_schedule() -> DailyWorkflowSchedule:
    values = _get_settings(_ENABLED_KEY, _TIME_KEY, _LAST_DATE_KEY)
    return DailyWorkflowSchedule(
        enabled=values.get(_ENABLED_KEY, "false").lower() == "true",
        time_local=_normalize_time(values.get(_TIME_KEY, _DEFAULT_TIME)),
        last_enqueued_date=values.get(_LAST_DATE_KEY, ""),
    )


def set_daily_workflow_schedule(enabled: bool, time_local: str) -> DailyWorkflowSchedule:
    normalized = _normalize_time(time_local)
    with session_scope() as session:
        _upsert_setting(session, _ENABLED_KEY, "true" if enabled else "false")
        _upsert_setting(session, _TIME_KEY, normalized)
    return get_daily_workflow_schedule()


def get_brand_profile_distillation_schedule() -> BrandProfileDistillationSchedule:
    values = _get_settings(_PROFILE_ENABLED_KEY, _PROFILE_TIME_KEY, _PROFILE_WEEKDAY_KEY, _PROFILE_LAST_DATE_KEY)
    return BrandProfileDistillationSchedule(
        enabled=values.get(_PROFILE_ENABLED_KEY, "false").lower() == "true",
        time_local=_normalize_time(values.get(_PROFILE_TIME_KEY, _DEFAULT_TIME)),
        weekday=_normalize_weekday(values.get(_PROFILE_WEEKDAY_KEY, "0")),
        last_enqueued_date=values.get(_PROFILE_LAST_DATE_KEY, ""),
    )


def set_brand_profile_distillation_schedule(
    enabled: bool,
    time_local: str,
    weekday: int,
) -> BrandProfileDistillationSchedule:
    normalized = _normalize_time(time_local)
    normalized_weekday = _normalize_weekday(str(weekday))
    with session_scope() as session:
        _upsert_setting(session, _PROFILE_ENABLED_KEY, "true" if enabled else "false")
        _upsert_setting(session, _PROFILE_TIME_KEY, normalized)
        _upsert_setting(session, _PROFILE_WEEKDAY_KEY, str(normalized_weekday))
    return get_brand_profile_distillation_schedule()


def get_recycling_schedule() -> RecyclingSchedule:
    values = _get_settings(_RECYCLE_ENABLED_KEY, _RECYCLE_DAY_KEY, _RECYCLE_TIME_KEY, _RECYCLE_LAST_MONTH_KEY)
    return RecyclingSchedule(
        enabled=values.get(_RECYCLE_ENABLED_KEY, "false").lower() == "true",
        day=_normalize_month_day(values.get(_RECYCLE_DAY_KEY, "1")),
        time_local=_normalize_time(values.get(_RECYCLE_TIME_KEY, _DEFAULT_TIME)),
        last_enqueued_month=values.get(_RECYCLE_LAST_MONTH_KEY, ""),
    )


def set_recycling_schedule(enabled: bool, day: int, time_local: str) -> RecyclingSchedule:
    normalized = _normalize_time(time_local)
    normalized_day = _normalize_month_day(str(day))
    with session_scope() as session:
        _upsert_setting(session, _RECYCLE_ENABLED_KEY, "true" if enabled else "false")
        _upsert_setting(session, _RECYCLE_DAY_KEY, str(normalized_day))
        _upsert_setting(session, _RECYCLE_TIME_KEY, normalized)
    return get_recycling_schedule()


def get_weekly_standup_schedule() -> WeeklyStandupSchedule:
    values = _get_settings(_STANDUP_ENABLED_KEY, _STANDUP_TIME_KEY, _STANDUP_WEEKDAY_KEY, _STANDUP_LAST_DATE_KEY)
    return WeeklyStandupSchedule(
        enabled=values.get(_STANDUP_ENABLED_KEY, "false").lower() == "true",
        time_local=_normalize_time(values.get(_STANDUP_TIME_KEY, _DEFAULT_TIME)),
        weekday=_normalize_weekday(values.get(_STANDUP_WEEKDAY_KEY, "0")),
        last_enqueued_date=values.get(_STANDUP_LAST_DATE_KEY, ""),
    )


def set_weekly_standup_schedule(enabled: bool, time_local: str, weekday: int) -> WeeklyStandupSchedule:
    normalized = _normalize_time(time_local)
    normalized_weekday = _normalize_weekday(str(weekday))
    with session_scope() as session:
        _upsert_setting(session, _STANDUP_ENABLED_KEY, "true" if enabled else "false")
        _upsert_setting(session, _STANDUP_TIME_KEY, normalized)
        _upsert_setting(session, _STANDUP_WEEKDAY_KEY, str(normalized_weekday))
    return get_weekly_standup_schedule()


def enqueue_daily_workflow(source: str) -> str:
    return job_queue.enqueue("run_daily_workflow", {"source": source})


def enqueue_brand_profile_distillation(source: str) -> str:
    return job_queue.enqueue("distill_brand_profile", {"source": source})


def enqueue_recycling(source: str) -> str:
    return job_queue.enqueue("recycle_top_posts", {"source": source})


def enqueue_weekly_standup(source: str) -> str:
    return job_queue.enqueue("weekly_standup", {"source": source})


def enqueue_due_daily_workflow(now: datetime | None = None) -> str | None:
    current = now or datetime.now()
    schedule = get_daily_workflow_schedule()
    if not schedule.enabled:
        return None
    if current.strftime("%H:%M") < schedule.time_local:
        return None
    today = current.date().isoformat()
    if schedule.last_enqueued_date == today:
        return None

    job_id = enqueue_daily_workflow("scheduler")
    with session_scope() as session:
        _upsert_setting(session, _LAST_DATE_KEY, today)
    return job_id


def enqueue_due_brand_profile_distillation(now: datetime | None = None) -> str | None:
    current = now or datetime.now()
    schedule = get_brand_profile_distillation_schedule()
    if not schedule.enabled:
        return None
    if current.weekday() != schedule.weekday:
        return None
    if current.strftime("%H:%M") < schedule.time_local:
        return None
    today = current.date().isoformat()
    if schedule.last_enqueued_date == today:
        return None

    job_id = enqueue_brand_profile_distillation("scheduler")
    with session_scope() as session:
        _upsert_setting(session, _PROFILE_LAST_DATE_KEY, today)
    return job_id


def enqueue_due_recycling(now: datetime | None = None) -> str | None:
    current = now or datetime.now()
    schedule = get_recycling_schedule()
    if not schedule.enabled:
        return None
    if current.day != schedule.day:
        return None
    if current.strftime("%H:%M") < schedule.time_local:
        return None
    month = current.strftime("%Y-%m")
    if schedule.last_enqueued_month == month:
        return None

    job_id = enqueue_recycling("scheduler")
    with session_scope() as session:
        _upsert_setting(session, _RECYCLE_LAST_MONTH_KEY, month)
    return job_id


def enqueue_due_weekly_standup(now: datetime | None = None) -> str | None:
    current = now or datetime.now()
    schedule = get_weekly_standup_schedule()
    if not schedule.enabled:
        return None
    if current.weekday() != schedule.weekday:
        return None
    if current.strftime("%H:%M") < schedule.time_local:
        return None
    today = current.date().isoformat()
    if schedule.last_enqueued_date == today:
        return None

    job_id = enqueue_weekly_standup("scheduler")
    with session_scope() as session:
        _upsert_setting(session, _STANDUP_LAST_DATE_KEY, today)
    return job_id


class DailyWorkflowScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="daily-workflow-scheduler")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                enqueue_due_daily_workflow()
                enqueue_due_brand_profile_distillation()
                enqueue_due_recycling()
                enqueue_due_weekly_standup()
            except Exception:
                logger.exception("Daily workflow scheduler tick failed")
            await asyncio.sleep(_POLL_SECONDS)


def _get_settings(*keys: str) -> dict[str, str]:
    with session_scope() as session:
        rows = session.query(SettingsKV).filter(SettingsKV.key.in_(keys)).all()
        return {row.key: row.value for row in rows}


def _upsert_setting(session, key: str, value: str) -> None:
    row = session.get(SettingsKV, key)
    if row is None:
        session.add(SettingsKV(key=key, value=value))
    else:
        row.value = value


def _normalize_time(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError("time_local must use HH:MM 24-hour format") from exc
    return parsed.strftime("%H:%M")


def _normalize_weekday(value: str) -> int:
    try:
        weekday = int(value)
    except ValueError as exc:
        raise ValueError("weekday must be an integer from 0 (Monday) to 6 (Sunday)") from exc
    if weekday < 0 or weekday > 6:
        raise ValueError("weekday must be an integer from 0 (Monday) to 6 (Sunday)")
    return weekday


def _normalize_month_day(value: str) -> int:
    try:
        day = int(value)
    except ValueError as exc:
        raise ValueError("day must be an integer from 1 to 28") from exc
    if day < 1 or day > 28:
        raise ValueError("day must be an integer from 1 to 28")
    return day


daily_workflow_scheduler = DailyWorkflowScheduler()
