"""Application settings, loaded from environment variables only (SRS §19: secrets via env)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.tz import validate_timezone


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GMI_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://gmi:gmi@localhost:5432/gmi"
    redis_url: str = "redis://localhost:6379/0"

    # Sessions / cookies
    session_ttl_hours: int = Field(default=12, ge=1, le=24 * 30)
    cookie_secure: bool = True
    session_cookie_name: str = "gmi_session"
    csrf_cookie_name: str = "gmi_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # Rate limiting (fixed window, per client IP)
    rate_limit_backend: Literal["redis", "memory"] = "redis"
    rate_limit_login_per_minute: int = 10
    rate_limit_default_per_minute: int = 300
    trust_proxy_headers: bool = False

    # Live ingestion (Phase 2). Off by default so tests/dev never call providers implicitly.
    ingestion_enabled: bool = False

    # Display default (storage is always UTC). Decision D8.
    default_timezone: str = "Asia/Gaza"

    # External provider credentials. Never returned by any API endpoint.
    twelvedata_api_key: SecretStr | None = None
    coingecko_demo_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    @field_validator("default_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        return validate_timezone(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()
