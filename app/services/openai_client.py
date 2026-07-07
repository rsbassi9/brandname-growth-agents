"""OpenAI client wrapper (P1-2c, P1-8).

Every OpenAI call in app/ must go through this wrapper so that:
- LOCAL_ONLY_AGENT_RUNS=true raises LocalOnlyModeError before any network call;
- an OpenAI-compatible provider (e.g. NVIDIA NIM) can be swapped in via
  BRAND_OPENAI_BASE_URL (see docs/NVIDIA_NIM.md).
"""

from __future__ import annotations

from typing import Any

from ..settings import get_settings


class GenerationError(RuntimeError):
    """A generation call failed. Raised instead of silently swallowing errors."""


class LocalOnlyModeError(RuntimeError):
    """Raised when an external AI call is attempted while local-only mode is on."""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            message
            or "LOCAL_ONLY_AGENT_RUNS=true: external OpenAI calls are disabled. "
            "Use the deterministic local fallback or disable local-only mode."
        )


def ensure_external_calls_allowed() -> None:
    if get_settings().local_only_agent_runs:
        raise LocalOnlyModeError()


def get_openai_client() -> Any:
    """Return a configured OpenAI client, honoring local-only mode and base URL."""
    ensure_external_calls_allowed()
    from openai import OpenAI

    settings = get_settings()
    kwargs: dict[str, Any] = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def resolve_model(premium: bool = False, override: str | None = None) -> str:
    """P1-8 two-tier model policy: cheap default everywhere, premium opt-in.

    - `override` (explicit per-call model) always wins;
    - `premium=True` uses BRAND_MODEL_PREMIUM when configured, otherwise falls
      back to the cheap default rather than failing the generation.
    """
    settings = get_settings()
    if override:
        return override
    if premium and settings.model_premium:
        return settings.model_premium
    return settings.model_default
