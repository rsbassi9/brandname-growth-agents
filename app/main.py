"""FastAPI application factory (P1-5).

Boots with NO environment variables set: SQLite is created at data/app.db,
local-only mode simply defaults off but no external call happens at startup.
"""

from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .db import init_db
from .routers import assets, calendar, campaigns, feed, jobs, library, playground, source_assets, strategy, system
from .services.backup import backup_loop
from .services.jobs import job_queue
from .services.scheduler import daily_workflow_scheduler
from .settings import ROOT_DIR, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await job_queue.start()
    await daily_workflow_scheduler.start()
    backup_task: asyncio.Task | None = None
    if get_settings().backup_enabled:
        backup_task = asyncio.create_task(backup_loop(), name="nightly-backup")
    try:
        yield
    finally:
        if backup_task is not None:
            backup_task.cancel()
            with suppress(asyncio.CancelledError):
                await backup_task
        await daily_workflow_scheduler.stop()
        await job_queue.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=f"{settings.brand_name} Growth Studio", lifespan=lifespan)

    api_prefix = "/api/v1"
    for router in (
        system.router,
        jobs.router,
        playground.router,
        assets.router,
        library.router,
        campaigns.router,
        calendar.router,
        feed.router,
        source_assets.router,
        strategy.router,
    ):
        app.include_router(router, prefix=api_prefix)

    # P2 serves the built frontend from frontend/dist when it exists.
    dist = ROOT_DIR / "frontend" / "dist"
    if dist.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()
