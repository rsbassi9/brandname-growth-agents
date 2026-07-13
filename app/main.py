"""FastAPI application factory (P1-5).

Boots with NO environment variables set: SQLite is created at data/app.db,
local-only mode simply defaults off but no external call happens at startup.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from .db import init_db
from .routers import (
    ads,
    assets,
    calendar,
    campaigns,
    feed,
    jobs,
    library,
    performance,
    playground,
    repurpose,
    seo,
    source_assets,
    strategy,
    system,
)
from .services.backup import backup_loop
from .services.jobs import job_queue
from .services.scheduler import daily_workflow_scheduler
from .settings import ROOT_DIR, get_settings

logger = logging.getLogger(__name__)


class SinglePageAppStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            request_path = str(scope.get("path", ""))
            if exc.status_code == 404 and not request_path.startswith("/api/"):
                return await super().get_response("index.html", scope)
            raise


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
        ads.router,
        jobs.router,
        playground.router,
        assets.router,
        library.router,
        performance.router,
        repurpose.router,
        seo.router,
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
        app.mount("/", SinglePageAppStaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()
