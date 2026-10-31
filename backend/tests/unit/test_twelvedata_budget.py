from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.ingestion.budget import TwelveDataSchedule, check_budget

H = D("0.9")


def test_schedule_arithmetic():
    s = TwelveDataSchedule(quote_interval_seconds=60, candles_1m_interval_seconds=300)
    # 2 symbols x (quote 1/min + 1m candles 1 + 1h candles 1) coinciding in one minute
    assert s.peak_credits_per_minute() == 6
    # 2 x (1440 + 288 + 24)
    assert s.credits_per_day() == 3504


def test_default_schedule_does_not_fit_basic_plan_daily_cap():
    r = check_budget(TwelveDataSchedule(60, 300), 8, 800, H)
    assert not r.ok and "credits/day" in r.message and "3504" in r.message


def test_default_schedule_fits_grow_29():
    r = check_budget(TwelveDataSchedule(60, 300), 55, 0, H)
    assert r.ok and r.limit_per_day is None


def test_fast_quotes_break_per_minute_limit():
    r = check_budget(TwelveDataSchedule(10, 60), 8, 0, H)  # peak = 2 x (6+1+1) = 16
    assert not r.ok and r.peak_per_minute == 16 and "credits/min" in r.message


def test_basic_plan_needs_sparse_schedule():
    # 2 x (ceil(86400/600)=144 + 86400/3600=24 + 24) = 384 <= 720
    assert check_budget(TwelveDataSchedule(600, 3600), 8, 800, H).ok


def test_settings_validation_fails_loudly_when_enabled(monkeypatch):
    monkeypatch.setenv("GMI_INGESTION_ENABLED", "true")
    monkeypatch.setenv("GMI_TWELVEDATA_API_KEY", "k")
    with pytest.raises(ValidationError, match="does not fit"):
        Settings()  # Basic defaults: 3504/day > 720
    monkeypatch.setenv("GMI_TWELVEDATA_CREDITS_PER_MINUTE", "55")
    monkeypatch.setenv("GMI_TWELVEDATA_CREDITS_PER_DAY", "0")
    assert Settings().twelvedata_credits_per_minute == 55


def test_no_validation_when_ingestion_disabled(monkeypatch):
    monkeypatch.setenv("GMI_TWELVEDATA_API_KEY", "k")
    assert Settings().ingestion_enabled is False
