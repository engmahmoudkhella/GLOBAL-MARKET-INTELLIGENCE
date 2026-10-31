"""Validated per-instrument configuration (stored in instruments.configuration_json).

Each market engine runs the same code with a different InstrumentConfig (SRS §4.3).
The config holds *configuration only* - never prices or model performance.
"""

from __future__ import annotations

from datetime import time
from datetime import time as TimeOfDay
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tz import validate_timezone

Horizon = Literal["1h", "4h", "24h", "7d", "30d"]
"""v1 forecast horizons (plan §0.2)."""

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WeeklyBoundary(_Strict):
    weekday: Weekday
    time: time


class DailyBreak(_Strict):
    start: time
    end: time


class SessionCalendar(_Strict):
    kind: Literal["continuous", "weekly"]
    timezone: str = "UTC"
    weekly_open: WeeklyBoundary | None = None
    weekly_close: WeeklyBoundary | None = None
    daily_breaks: tuple[DailyBreak, ...] = ()
    provisional: bool = Field(
        default=True,
        description="True until replaced by provider-defined sessions and holiday data (Phase 2).",
    )

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return validate_timezone(v)

    @model_validator(mode="after")
    def _shape(self) -> SessionCalendar:
        if self.kind == "weekly" and (self.weekly_open is None or self.weekly_close is None):
            raise ValueError("weekly sessions need weekly_open and weekly_close")
        if self.kind == "continuous" and (
            self.weekly_open or self.weekly_close or self.daily_breaks
        ):
            raise ValueError("continuous sessions cannot define open/close/breaks")
        return self


class DailyBoundary(_Strict):
    """Wall-clock time at which one trading day ends and the next begins.

    Our own daily candles are built from intraday bars between consecutive boundaries; provider
    daily bars are never stored (their boundaries are provider-defined)."""

    timezone: str = "UTC"
    time: TimeOfDay = TimeOfDay(0, 0)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return validate_timezone(v)


class InstrumentConfig(_Strict):
    schema_version: Literal[1] = 1
    sessions: SessionCalendar
    price_precision: int = Field(ge=0, le=10)
    staleness_seconds: int = Field(gt=0, le=7 * 24 * 3600)
    max_spread_bps: Decimal | None = Field(default=None, gt=0)
    candle_timeframes: tuple[Timeframe, ...]
    forecasting_enabled: bool
    forecast_horizons: tuple[Horizon, ...] = ()
    daily_candle_boundary: DailyBoundary = DailyBoundary()
    notes: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> InstrumentConfig:
        if len(set(self.forecast_horizons)) != len(self.forecast_horizons):
            raise ValueError("duplicate forecast horizons")
        if len(set(self.candle_timeframes)) != len(self.candle_timeframes):
            raise ValueError("duplicate candle timeframes")
        if self.forecasting_enabled and not self.forecast_horizons:
            raise ValueError("forecasting_enabled requires at least one horizon")
        if not self.forecasting_enabled and self.forecast_horizons:
            raise ValueError("horizons configured but forecasting is disabled")
        return self
