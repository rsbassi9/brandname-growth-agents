"""OpenAI client wrapper: local-only guard, base-url passthrough, model tiers (P1-2c, P1-8)."""

from __future__ import annotations

import pytest


def test_local_only_mode_blocks_client(app_env) -> None:
    from app.services.openai_client import LocalOnlyModeError, get_openai_client

    with pytest.raises(LocalOnlyModeError):
        get_openai_client()


def test_local_only_mode_blocks_agent_runs(app_env) -> None:
    import asyncio

    from app.services.agents import run_agent
    from app.services.openai_client import LocalOnlyModeError

    with pytest.raises(LocalOnlyModeError):
        asyncio.run(run_agent(object(), "prompt"))


def test_base_url_passthrough(app_env, monkeypatch) -> None:
    """BRAND_OPENAI_BASE_URL (e.g. NVIDIA NIM, Ollama) reaches the OpenAI ctor."""
    import openai

    from app.settings import reset_settings_cache

    captured: dict = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("LOCAL_ONLY_AGENT_RUNS", "false")
    monkeypatch.setenv("BRAND_OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("BRAND_OPENAI_API_KEY", "nvapi-test-not-real")
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    reset_settings_cache()

    from app.services.openai_client import get_openai_client

    get_openai_client()
    assert captured["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert captured["api_key"] == "nvapi-test-not-real"


def test_resolve_model_default_tier(app_env, monkeypatch) -> None:
    from app.services.openai_client import resolve_model
    from app.settings import reset_settings_cache

    monkeypatch.setenv("BRAND_MODEL_DEFAULT", "cheap-model")
    monkeypatch.delenv("BRAND_MODEL_PREMIUM", raising=False)
    reset_settings_cache()
    assert resolve_model() == "cheap-model"
    # Premium requested but not configured: fall back to cheap, never fail.
    assert resolve_model(premium=True) == "cheap-model"


def test_resolve_model_premium_and_override(app_env, monkeypatch) -> None:
    from app.services.openai_client import resolve_model
    from app.settings import reset_settings_cache

    monkeypatch.setenv("BRAND_MODEL_DEFAULT", "cheap-model")
    monkeypatch.setenv("BRAND_MODEL_PREMIUM", "premium-model")
    reset_settings_cache()
    assert resolve_model() == "cheap-model"
    assert resolve_model(premium=True) == "premium-model"
    assert resolve_model(premium=True, override="explicit-model") == "explicit-model"


def test_generation_error_is_typed(app_env) -> None:
    from app.services.openai_client import GenerationError

    assert issubclass(GenerationError, RuntimeError)
