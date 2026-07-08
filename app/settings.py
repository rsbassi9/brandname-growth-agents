"""Application settings (pydantic-settings, env prefix BRAND_).

Real environment variables always beat the repo .env file (pydantic-settings
gives init/env priority over dotenv values), which keeps the P0-2 fix intact.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BRAND_",
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # P1-7: single source of truth for the brand strings; never hardcode them in app/.
    brand_name: str = Field(
        default="BRAND NAME",
        validation_alias=AliasChoices("BRAND_NAME", "BRAND_BRAND_NAME"),
    )
    shopify_url: str = Field(
        default="https://www.brandnamedesign.co/",
        validation_alias=AliasChoices("BRAND_SHOPIFY_URL", "BRAND_WEBSITE_URL"),
    )

    # Database. Empty means "sqlite at <data_dir>/app.db".
    database_url: str = ""
    data_dir: str = ""

    # Safety flag honored by every execution path (accepts legacy unprefixed name).
    local_only_agent_runs: bool = Field(
        default=False,
        validation_alias=AliasChoices("LOCAL_ONLY_AGENT_RUNS", "BRAND_LOCAL_ONLY_AGENT_RUNS"),
    )

    # OpenAI (accepts the legacy unprefixed names too).
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    # P1-8: optional OpenAI-compatible provider base URL (e.g. NVIDIA NIM).
    openai_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
    )
    # P1-8: two-tier model policy (owner cost directive). The cheap default is
    # used everywhere unless a call explicitly opts into the premium tier.
    model_default: str = Field(
        default="gpt-5.4-mini",
        validation_alias=AliasChoices("BRAND_MODEL_DEFAULT", "BRAND_TEXT_MODEL", "OPENAI_MODEL"),
    )
    model_premium: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_MODEL_PREMIUM",),
    )
    # P1-2a: image model comes from settings, never hardcoded.
    image_model: str = Field(
        default="gpt-image-1",
        validation_alias=AliasChoices("BRAND_IMAGE_MODEL", "IMAGE_CONCEPT_MODEL"),
    )
    image_size: str = Field(
        default="1024x1536",
        validation_alias=AliasChoices("BRAND_IMAGE_SIZE", "IMAGE_CONCEPT_SIZE"),
    )
    image_quality: str = Field(
        default="medium",
        validation_alias=AliasChoices("BRAND_IMAGE_QUALITY", "IMAGE_CONCEPT_QUALITY"),
    )
    image_concept_count: int = Field(
        default=3,
        validation_alias=AliasChoices("BRAND_IMAGE_CONCEPT_COUNT", "IMAGE_CONCEPT_COUNT"),
    )
    ai_image_generation_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BRAND_AI_IMAGE_GENERATION_ENABLED", "AI_IMAGE_GENERATION_ENABLED"),
    )

    # Optional TTS. Defaults keep P4-2 stub-first and test-safe.
    tts_provider: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_TTS_PROVIDER", "TTS_PROVIDER"),
    )
    elevenlabs_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"),
    )
    elevenlabs_voice_id: str = Field(
        default="",
        validation_alias=AliasChoices("BRAND_ELEVENLABS_VOICE_ID", "ELEVENLABS_VOICE_ID"),
    )
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        validation_alias=AliasChoices("BRAND_ELEVENLABS_MODEL_ID", "ELEVENLABS_MODEL_ID"),
    )

    # Shopify Admin API (legacy env names accepted). The public store URL is
    # `shopify_url` above.
    shopify_store_domain: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_STORE_DOMAIN", "BRAND_SHOPIFY_STORE_DOMAIN")
    )
    shopify_admin_access_token: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_ADMIN_ACCESS_TOKEN", "BRAND_SHOPIFY_ADMIN_ACCESS_TOKEN")
    )
    shopify_api_version: str = Field(
        default="2025-04", validation_alias=AliasChoices("SHOPIFY_API_VERSION", "BRAND_SHOPIFY_API_VERSION")
    )
    shopify_write_enabled: bool = Field(
        default=False, validation_alias=AliasChoices("SHOPIFY_WRITE_ENABLED", "BRAND_SHOPIFY_WRITE_ENABLED")
    )

    # Google Drive (legacy env names accepted).
    google_drive_enabled: bool = Field(
        default=False, validation_alias=AliasChoices("GOOGLE_DRIVE_ENABLED", "BRAND_GOOGLE_DRIVE_ENABLED")
    )
    google_drive_root_folder_id: str = Field(
        default="", validation_alias=AliasChoices("GOOGLE_DRIVE_ROOT_FOLDER_ID", "BRAND_GOOGLE_DRIVE_ROOT_FOLDER_ID")
    )
    google_auth_mode: str = Field(
        default="oauth", validation_alias=AliasChoices("GOOGLE_AUTH_MODE", "BRAND_GOOGLE_AUTH_MODE")
    )
    google_application_credentials: str = Field(
        default="credentials.json",
        validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS", "BRAND_GOOGLE_APPLICATION_CREDENTIALS"),
    )
    google_oauth_client_file: str = Field(
        default="oauth_client.json",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_FILE", "BRAND_GOOGLE_OAUTH_CLIENT_FILE"),
    )
    google_oauth_token_file: str = Field(
        default="token.json",
        validation_alias=AliasChoices("GOOGLE_OAUTH_TOKEN_FILE", "BRAND_GOOGLE_OAUTH_TOKEN_FILE"),
    )

    # P1-9: nightly DB backup.
    backup_enabled: bool = True
    backup_keep: int = 7

    def resolved_data_dir(self) -> Path:
        raw = self.data_dir or os.getenv("DATA_DIR", "")
        return Path(raw).resolve() if raw else (ROOT_DIR / "data")

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.resolved_data_dir() / "app.db"
        return f"sqlite:///{db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Test helper: force re-read of environment on next get_settings()."""
    get_settings.cache_clear()
