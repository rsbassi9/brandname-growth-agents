"""Settings defaults, env priority (P0-2 regression), and brand directives (P1-7)."""

from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_brand_defaults(app_env) -> None:
    from app.settings import get_settings

    settings = get_settings()
    assert settings.brand_name == "BRAND NAME"
    assert settings.shopify_url == "https://www.brandnamedesign.co/"


def test_env_overrides_brand_settings(app_env, monkeypatch) -> None:
    from app.settings import get_settings, reset_settings_cache

    monkeypatch.setenv("BRAND_NAME", "OTHER LABEL")
    monkeypatch.setenv("BRAND_SHOPIFY_URL", "https://example.com/")
    reset_settings_cache()
    settings = get_settings()
    assert settings.brand_name == "OTHER LABEL"
    assert settings.shopify_url == "https://example.com/"


def test_real_env_beats_dotenv(app_env, monkeypatch) -> None:
    """P0-2 regression: real environment variables win over any .env value."""
    from app.settings import get_settings, reset_settings_cache

    monkeypatch.setenv("OPENAI_API_KEY", "from-real-env")
    reset_settings_cache()
    assert get_settings().openai_api_key == "from-real-env"


def test_two_tier_model_settings(app_env, monkeypatch) -> None:
    from app.settings import get_settings, reset_settings_cache

    monkeypatch.setenv("BRAND_MODEL_DEFAULT", "cheap-model")
    monkeypatch.setenv("BRAND_MODEL_PREMIUM", "expensive-model")
    reset_settings_cache()
    settings = get_settings()
    assert settings.model_default == "cheap-model"
    assert settings.model_premium == "expensive-model"


def test_image_model_from_settings(app_env, monkeypatch) -> None:
    """P1-2a regression: image model is configurable, defaults to gpt-image-1."""
    from app.settings import get_settings, reset_settings_cache

    assert get_settings().image_model == "gpt-image-1"
    monkeypatch.setenv("BRAND_IMAGE_MODEL", "custom-image-model")
    reset_settings_cache()
    assert get_settings().image_model == "custom-image-model"


def test_no_hardcoded_brand_strings_in_app() -> None:
    """P1-7: brand name/store URL appear only as settings defaults."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path.name == "settings.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "BRAND NAME" in text or "brandnamedesign.co" in text:
            offenders.append(str(path))
    assert offenders == []


def test_no_silent_exception_swallowing_in_app() -> None:
    """P1-2b/P1-3: no `except ...: pass` anywhere in app/."""
    import re

    offenders = []
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"except[^\n]*:\s*\n\s*pass\b", text):
            offenders.append(str(path))
    assert offenders == []
