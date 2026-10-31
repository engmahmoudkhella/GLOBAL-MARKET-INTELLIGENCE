from datetime import UTC, datetime, timedelta

from app.instruments.config_schema import SessionCalendar
from app.markets.sessions import MarketCalendar

FX = MarketCalendar(
    SessionCalendar.model_validate(
        {
            "kind": "weekly",
            "timezone": "America/New_York",
            "weekly_open": {"weekday": "sun", "time": "17:00"},
            "weekly_close": {"weekday": "fri", "time": "17:00"},
        }
    )
)
GOLD = MarketCalendar(
    SessionCalendar.model_validate(
        {
            "kind": "weekly",
            "timezone": "America/New_York",
            "weekly_open": {"weekday": "sun", "time": "18:00"},
            "weekly_close": {"weekday": "fri", "time": "17:00"},
            "daily_breaks": [{"start": "17:00", "end": "18:00"}],
        }
    )
)
CRYPTO = MarketCalendar(SessionCalendar.model_validate({"kind": "continuous"}))


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def test_fx_weekly_boundaries_winter_and_summer():
    # 2026-11-06 is a Friday; New York is on EST (UTC-5) -> close 22:00 UTC.
    assert FX.is_open(utc(2026, 11, 6, 21, 59))
    assert not FX.is_open(utc(2026, 11, 6, 22, 0))
    assert not FX.is_open(utc(2026, 11, 7, 12, 0))  # Saturday
    # Sunday 2026-11-08 opens 17:00 EST = 22:00 UTC
    assert not FX.is_open(utc(2026, 11, 8, 21, 59))
    assert FX.is_open(utc(2026, 11, 8, 22, 0))
    # Summer (EDT, UTC-4): Friday 2026-07-10 closes 21:00 UTC
    assert FX.is_open(utc(2026, 7, 10, 20, 59))
    assert not FX.is_open(utc(2026, 7, 10, 21, 0))
    # Midweek always open
    assert FX.is_open(utc(2026, 11, 4, 3, 0))


def test_gold_daily_break():
    # Wednesday 2026-11-04 17:30 EST = 22:30 UTC -> in the daily break
    assert not GOLD.is_open(utc(2026, 11, 4, 22, 30))
    assert GOLD.is_open(utc(2026, 11, 4, 23, 0))
    # Sunday open is 18:00 for gold
    assert not GOLD.is_open(utc(2026, 11, 8, 22, 30))
    assert GOLD.is_open(utc(2026, 11, 8, 23, 0))


def test_crypto_always_open():
    assert CRYPTO.is_open(utc(2026, 11, 7, 12, 0))


def test_is_open_during_window():
    # 1h bar starting Friday 21:30 UTC (winter): open for its first 30 minutes
    assert FX.is_open_during(utc(2026, 11, 6, 21, 30), timedelta(hours=1))
    assert not FX.is_open_during(utc(2026, 11, 7, 10, 0), timedelta(hours=4))


def test_naive_timestamp_rejected():
    import pytest

    with pytest.raises(ValueError):
        FX.is_open(datetime(2026, 11, 4, 3, 0))  # noqa: DTZ001
