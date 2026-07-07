"""Nightly SQLite backup (P1-9).

A lifespan task copies data/app.db to data/backups/app-YYYYMMDD.db once per
night and keeps only the newest `backup_keep` files (default 7).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from ..settings import get_settings

logger = logging.getLogger(__name__)


def run_backup(
    db_path: Path | None = None,
    backups_dir: Path | None = None,
    keep: int | None = None,
    now: datetime | None = None,
) -> Path | None:
    """Copy the DB file to backups/app-YYYYMMDD.db and prune old backups.

    Returns the backup path, or None when there is nothing to back up yet.
    """
    settings = get_settings()
    if db_path is None:
        db_path = settings.resolved_data_dir() / "app.db"
    if backups_dir is None:
        backups_dir = settings.resolved_data_dir() / "backups"
    if keep is None:
        keep = settings.backup_keep
    if not db_path.exists():
        logger.info("No database at %s yet; skipping backup", db_path)
        return None

    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d")
    target = backups_dir / f"app-{stamp}.db"
    shutil.copy2(db_path, target)
    logger.info("Backed up %s -> %s", db_path, target)

    prune_backups(backups_dir, keep)
    return target


def prune_backups(backups_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` app-*.db files; returns deletions."""
    backups = sorted(backups_dir.glob("app-*.db"), key=lambda path: path.name, reverse=True)
    removed: list[Path] = []
    for stale in backups[max(keep, 0) :]:
        stale.unlink()
        removed.append(stale)
        logger.info("Pruned old backup %s", stale)
    return removed


def _seconds_until_next_run(now: datetime | None = None) -> float:
    """Next run at 00:05 local time."""
    now = now or datetime.now()
    target = now.replace(hour=0, minute=5, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def backup_loop() -> None:
    """Lifespan task: back up once at startup, then nightly at 00:05."""
    try:
        await asyncio.to_thread(run_backup)
    except Exception:
        logger.exception("Startup backup failed; will retry on the nightly schedule")
    while True:
        await asyncio.sleep(_seconds_until_next_run())
        try:
            await asyncio.to_thread(run_backup)
        except Exception:
            # Explicit fallback: a failed nightly backup is logged and retried
            # the next night; it must never take the app down.
            logger.exception("Nightly backup failed")
