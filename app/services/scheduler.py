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
_DEFAULT_TIME = "09:00"
_POLL_SECONDS = 30


@dataclass(frozen=True)
class DailyWorkflowSchedule:
    enabled: bool
    time_local: str
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


def enqueue_daily_workflow(source: str) -> str:
    return job_queue.enqueue("run_daily_workflow", {"source": source})


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


daily_workflow_scheduler = DailyWorkflowScheduler()
