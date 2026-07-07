"""Nightly backup task (P1-9): dated copy + keep-newest-7 pruning."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def test_backup_creates_dated_copy(app_env, tmp_path: Path) -> None:
    from app.services.backup import run_backup

    db_path = tmp_path / "db" / "app.db"
    db_path.parent.mkdir(parents=True)
    db_path.write_bytes(b"sqlite-bytes")
    backups = tmp_path / "backups"

    target = run_backup(db_path=db_path, backups_dir=backups, keep=7, now=datetime(2026, 7, 6))
    assert target == backups / "app-20260706.db"
    assert target.read_bytes() == b"sqlite-bytes"


def test_backup_skips_when_db_missing(app_env, tmp_path: Path) -> None:
    from app.services.backup import run_backup

    result = run_backup(db_path=tmp_path / "missing.db", backups_dir=tmp_path / "backups", keep=7)
    assert result is None
    assert not (tmp_path / "backups").exists()


def test_backup_prunes_to_newest_seven(app_env, tmp_path: Path) -> None:
    from app.services.backup import run_backup

    db_path = tmp_path / "app.db"
    db_path.write_bytes(b"x")
    backups = tmp_path / "backups"
    backups.mkdir()
    for day in range(1, 10):  # app-20260601.db .. app-20260609.db
        (backups / f"app-202606{day:02}.db").write_bytes(b"old")

    run_backup(db_path=db_path, backups_dir=backups, keep=7, now=datetime(2026, 7, 6))
    remaining = sorted(path.name for path in backups.glob("app-*.db"))
    assert len(remaining) == 7
    assert remaining[-1] == "app-20260706.db"
    assert "app-20260601.db" not in remaining
    assert "app-20260602.db" not in remaining
    assert "app-20260603.db" not in remaining


def test_backup_is_idempotent_same_day(app_env, tmp_path: Path) -> None:
    from app.services.backup import run_backup

    db_path = tmp_path / "app.db"
    db_path.write_bytes(b"one")
    backups = tmp_path / "backups"
    run_backup(db_path=db_path, backups_dir=backups, keep=7, now=datetime(2026, 7, 6))
    db_path.write_bytes(b"two")
    run_backup(db_path=db_path, backups_dir=backups, keep=7, now=datetime(2026, 7, 6))
    files = list(backups.glob("app-*.db"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"two"
