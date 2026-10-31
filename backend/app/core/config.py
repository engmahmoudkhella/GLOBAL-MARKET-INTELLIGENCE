"""Application settings, loaded from environment variables only (SRS §19: secrets via env)."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.tz import validate_timezone

if TYPE_CHECKING:
    from app.ingestion.budget import TwelveDataSchedule


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

    # Twelve Data plan limits. Defaults = free Basic plan (development only: 8 credits/min,
    # 800/day, non-display). Grow $29: GMI_TWELVEDATA_CREDITS_PER_MINUTE=55 and
    # GMI_TWELVEDATA_CREDITS_PER_DAY=0 (0 = no daily cap).
    twelvedata_credits_per_minute: int = Field(default=8, ge=1)
    twelvedata_credits_per_day: int = Field(default=800, ge=0)
    twelvedata_quote_interval_seconds: int = Field(default=60, ge=10)
    twelvedata_candles_1m_interval_seconds: int = Field(default=300, ge=60, le=3600)
    twelvedata_budget_headroom: Decimal = Field(default=Decimal("0.9"), gt=0, le=1)

    # USD/ILS cross-check: Twelve Data price near BoI publication vs BoI representative rate.
    boi_crosscheck_threshold_pct: Decimal = Field(default=Decimal("0.5"), gt=0)
    boi_crosscheck_window_minutes: int = Field(default=15, ge=1, le=120)
    # Used when the BoI response carries no publication timestamp (SDMX history).
    # ASSUMPTION to verify against BoI's published schedule.
    boi_publication_fallback_time: time = time(15, 30)

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

    @model_validator(mode="after")
    def _twelvedata_budget(self) -> Settings:
        """Fail loudly at startup if the live schedule cannot fit the Twelve Data plan."""
        if self.ingestion_enabled and self.twelvedata_api_key is not None:
            from app.ingestion.budget import check_budget

            result = check_budget(
                self.twelvedata_schedule(),
                self.twelvedata_credits_per_minute,
                self.twelvedata_credits_per_day,
                self.twelvedata_budget_headroom,
            )
            if not result.ok:
                raise ValueError(result.message)
        return self

    def twelvedata_schedule(self) -> TwelveDataSchedule:
        from app.ingestion.budget import TwelveDataSchedule

        return TwelveDataSchedule(
            self.twelvedata_quote_interval_seconds, self.twelvedata_candles_1m_interval_seconds
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
