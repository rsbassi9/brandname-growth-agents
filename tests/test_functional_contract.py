"""Harness safety contracts; no live credentials or network required."""
from pathlib import Path

import pytest


def test_functional_environment_never_inherits_credentials(tmp_path, monkeypatch):
    from scripts.functional_stack import environment

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_FILE", "/private/real-token.json")
    env = environment(tmp_path)
    assert env["LOCAL_ONLY_AGENT_RUNS"] == "true"
    assert env["GOOGLE_DRIVE_ENABLED"] == "false"
    assert env["SHOPIFY_WRITE_ENABLED"] == "false"
    assert env["BRAND_BACKUP_ENABLED"] == "false"
    assert "synthetic-secret" not in str(env)
    assert "/private/real-token.json" not in str(env)
    assert Path(env["DATA_DIR"]).is_relative_to(tmp_path)


def test_cleanup_rejects_broad_or_foreign_targets(tmp_path):
    from scripts.functional_stack import validate_root

    for path in (Path("/"), Path.home(), tmp_path, tmp_path / "ari-growth-stack-forged"):
        with pytest.raises(ValueError):
            validate_root(path, "synthetic-marker")
