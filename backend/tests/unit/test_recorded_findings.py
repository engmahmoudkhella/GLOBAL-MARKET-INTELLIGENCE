"""Owner's live recordings 2026-10-31 (browser, Gaza): findings F, G, H, I."""

import json
import logging
import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest

from app.ingestion.budget import TwelveDataSchedule, check_against_plan
from app.providers import parsing
from app.providers.coinbase import CoinbaseExchangeProvider
from app.providers.errors import ProviderDataError
from app.providers.twelvedata import TwelveDataProvider, parse_plan

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
H = D("0.9")


def fx(name):
    return (FIX / name).read_text()


def coinbase(path, body, now):
    return CoinbaseExchangeProvider(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=body) if r.url.path == path else httpx.Response(404)
        ),
        sleep=lambda s: None,
        clock=lambda: now,
    )


def twelvedata(body, now):
    return TwelveDataProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: now,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=body)),
    )


# --- F: Coinbase ticker -------------------------------------------------------------------
@pytest.mark.parametrize(
    "fixture,observed,mid",
    [
        (
            "coinbase_ticker.recorded-2026-10-31a.json",
            datetime(2026, 10, 31, 10, 57, 19, 430993, tzinfo=UTC),
            D("77284.235"),
        ),  # 9 digits
        (
            "coinbase_ticker.recorded-2026-10-31b.json",
            datetime(2026, 10, 31, 10, 57, 52, 563651, tzinfo=UTC),
            D("77274.615"),
        ),  # 6 digits
    ],
)
def test_recorded_ticker_true_mid_and_both_time_precisions(fixture, observed, mid):
    q = coinbase(
        "/products/BTC-USD/ticker", fx(fixture), observed + timedelta(seconds=1)
    ).get_latest_quote("BTC-USD")
    assert q.observed_at == observed and q.mid == mid
    assert (q.bid, q.ask) == (D(json.loads(fx(fixture))["bid"]), D(json.loads(fx(fixture))["ask"]))


def test_unknown_ticker_field_ignored_and_logged_once(caplog):
    parsing._UNKNOWN_FIELDS_LOGGED.clear()
    caplog.set_level(logging.INFO, logger="app.providers")
    now = datetime(2026, 10, 31, 10, 58, tzinfo=UTC)
    for f in (
        "coinbase_ticker.recorded-2026-10-31a.json",
        "coinbase_ticker.recorded-2026-10-31b.json",
    ):
        coinbase("/products/BTC-USD/ticker", fx(f), now).get_latest_quote("BTC-USD")
    msgs = [r.getMessage() for r in caplog.records if "unknown field" in r.getMessage()]
    assert msgs == ["coinbase ticker: ignoring unknown field 'rfq_volume'"]


@pytest.mark.parametrize(
    "old,new",
    [
        ('"bid":"77284.23"', '"bid":77284.23'),  # number where a string is required
        ('"ask":"77284.24"', '"ask":"n/a"'),
    ],
)
def test_ticker_required_field_types_strict(old, new):
    body = fx("coinbase_ticker.recorded-2026-10-31a.json").replace(old, new)
    with pytest.raises(ProviderDataError):
        coinbase(
            "/products/BTC-USD/ticker", body, datetime(2026, 10, 31, 11, tzinfo=UTC)
        ).get_latest_quote("BTC-USD")


# --- G: Coinbase candles [time, LOW, HIGH, OPEN, CLOSE, volume] -----------------------------
FETCHED = datetime(2026, 10, 31, 10, 57, 30, tzinfo=UTC)


def test_recorded_candles_mapped_by_explicit_column_order():
    cs = coinbase(
        "/products/BTC-USD/candles",
        fx("coinbase_candles_1h.recorded-2026-10-31.partial.json"),
        FETCHED,
    ).get_intraday_ohlcv("BTC-USD", "1h", FETCHED - timedelta(hours=4), FETCHED)
    assert [c.open_time.hour for c in cs] == [8, 9, 10]  # sorted ascending from newest-first
    c10 = cs[-1]
    assert c10.open_time == datetime(2026, 10, 31, 10, tzinfo=UTC)  # 1793440800
    assert (c10.low, c10.high, c10.open, c10.close, c10.volume) == (
        D("77237.54"),
        D("77404.77"),
        D("77319.35"),
        D("77300.78"),
        D("68.49745375"),
    )
    # Current hour (ends 11:00 > response 10:57:30) is flagged incomplete; ingestion drops it.
    assert [c.is_complete for c in cs] == [True, True, False]


def test_swapped_columns_detected():
    # OPEN and LOW swapped -> low > open: column order changed, reject
    body = "[[1793440800,77319.35,77404.77,77237.54,77300.78,68.49745375]]"
    with pytest.raises(ProviderDataError, match="column order"):
        coinbase("/products/BTC-USD/candles", body, FETCHED).get_intraday_ohlcv(
            "BTC-USD", "1h", FETCHED - timedelta(hours=2), FETCHED
        )


def test_candle_strings_rejected():
    body = '[[1793440800,"77237.54",77404.77,77319.35,77300.78,68.49745375]]'
    with pytest.raises(ProviderDataError):
        coinbase("/products/BTC-USD/candles", body, FETCHED).get_intraday_ohlcv(
            "BTC-USD", "1h", FETCHED - timedelta(hours=2), FETCHED
        )


# --- H: Twelve Data time_series without UTC ------------------------------------------------
TD_RECEIVED = datetime(2026, 10, 31, 10, 58, 59, tzinfo=UTC)


def test_recorded_non_utc_series_rejected_as_future():
    body = fx("twelvedata_time_series_1h_no_tz.recorded-2026-10-31.json")
    with pytest.raises(ProviderDataError, match="future"):
        twelvedata(body, TD_RECEIVED).get_intraday_ohlcv(
            "USD/ILS", "1h", TD_RECEIVED - timedelta(hours=12), TD_RECEIVED
        )


def utc_shifted_series():
    """Same recorded values with UTC labels 06:00-10:00 (what timezone=UTC returns).
    meta has no timezone field, exactly like the recording."""
    data = json.loads(fx("twelvedata_time_series_1h_no_tz.recorded-2026-10-31.json"))
    for v, hour in zip(data["values"], (10, 9, 8, 7, 6), strict=True):
        v["datetime"] = f"2026-10-31 {hour:02d}:00:00"
    return json.dumps(data)


def test_utc_series_without_meta_timezone_accepted_latest_incomplete():
    seen = []
    p = TwelveDataProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: TD_RECEIVED,
        transport=httpx.MockTransport(
            lambda r: seen.append(r) or httpx.Response(200, text=utc_shifted_series())
        ),
    )
    cs = p.get_intraday_ohlcv("USD/ILS", "1h", TD_RECEIVED - timedelta(hours=12), TD_RECEIVED)
    assert seen[0].url.params["timezone"] == "UTC"
    assert [c.open_time.hour for c in cs] == [6, 7, 8, 9, 10]
    assert [c.is_complete for c in cs] == [True, True, True, True, False]
    assert cs[-1].close == D("3.14403")


# --- I: Twelve Data plan from /api_usage ---------------------------------------------------
def test_recorded_api_usage_parsed():
    plan = parse_plan(json.loads(fx("twelvedata_api_usage.recorded-2026-10-31.json")))
    assert (plan.category, plan.per_minute, plan.per_day, plan.current_usage, plan.daily_usage) == (
        "basic",
        8,
        800,
        2,
        4,
    )


def test_plan_check_rejects_grow_config_on_basic_key():
    r = check_against_plan(TwelveDataSchedule(60, 300), 55, 0, H, 8, 800, "basic")
    assert not r.ok
    assert "exceeds the basic plan's 8/min" in r.message
    assert "unlimited exceeds the basic plan's 800/day" in r.message


def test_plan_check_default_schedule_does_not_fit_basic_even_if_configured_right():
    r = check_against_plan(TwelveDataSchedule(60, 300), 8, 800, H, 8, 800, "basic")
    assert not r.ok and "3504 credits/day" in r.message


def test_plan_check_sparse_schedule_fits_basic_and_default_fits_grow():
    assert check_against_plan(TwelveDataSchedule(600, 3600), 8, 800, H, 8, 800, "basic").ok
    assert check_against_plan(TwelveDataSchedule(60, 300), 55, 0, H, 55, 0, "grow").ok


def test_beat_startup_plan_verification(monkeypatch):
    from pydantic import SecretStr

    from app.core.config import Settings
    from app.tasks import celery_app as ca

    class FakeTD:
        def __init__(self, *a, **k):
            pass

        def get_plan(self):
            return parse_plan(json.loads(fx("twelvedata_api_usage.recorded-2026-10-31.json")))

        def close(self):
            pass

    monkeypatch.setattr("app.providers.twelvedata.TwelveDataProvider", FakeTD)
    base = Settings().model_dump()
    s = Settings.model_construct(
        **{
            **base,
            "ingestion_enabled": True,
            "twelvedata_api_key": SecretStr("k"),
            "twelvedata_credits_per_minute": 55,
            "twelvedata_credits_per_day": 0,
        }
    )
    with pytest.raises(RuntimeError, match="basic plan"):
        ca.verify_twelvedata_plan(s)
    ok = Settings.model_construct(
        **{
            **base,
            "ingestion_enabled": True,
            "twelvedata_api_key": SecretStr("k"),
            "twelvedata_quote_interval_seconds": 600,
            "twelvedata_candles_1m_interval_seconds": 3600,
        }
    )
    assert "plan basic ok" in ca.verify_twelvedata_plan(ok)
    assert ca.verify_twelvedata_plan(Settings()) is None  # ingestion disabled
