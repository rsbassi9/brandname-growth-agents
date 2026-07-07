from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reset_runtime() -> None:
    from app.db import reset_engine
    from app.settings import reset_settings_cache

    reset_settings_cache()
    reset_engine()


@pytest.fixture
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated environment: tmp DB, tmp data dir, local-only mode ON."""
    db_path = tmp_path / "data" / "app.db"
    monkeypatch.setenv("BRAND_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOCAL_ONLY_AGENT_RUNS", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("BRAND_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("BRAND_OPENAI_API_KEY", raising=False)
    # The developer's .env may enable Google Drive: tests never call it live.
    monkeypatch.setenv("GOOGLE_DRIVE_ENABLED", "false")
    monkeypatch.setenv("SHOPIFY_WRITE_ENABLED", "false")
    _reset_runtime()
    yield tmp_path
    _reset_runtime()


@pytest.fixture
def client(app_env: Path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
