import json
import logging
import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest

from app.providers.errors import (
    CapabilityNotSupported,
    ProviderDataError,
    ProviderRateLimited,
    ProviderRejected,
)
from app.providers.twelvedata import TwelveDataProvider

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
RECEIVED = datetime(2026, 10, 31, 10, 27, 30, tzinfo=UTC)
KEY = "td-test-key-should-not-leak"


def fx(name):
    return (FIX / name).read_text()


def provider(routes, seen=None, now=RECEIVED):
    def handler(req):
        if seen is not None:
            seen.append(req)
        body = routes.get(req.url.path)
        if callable(body):
            body = body(req)
        return httpx.Response(200, text=body) if body is not None else httpx.Response(404)

    return TwelveDataProvider(
        api_key=KEY, transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: now
    )


@pytest.mark.parametrize(
    "fixture,symbol,close",
    [
        ("twelvedata_quote_usdils.recorded-2026-10-31.json", "USD/ILS", D("3.14153")),
        ("twelvedata_quote_xauusd.recorded-2026-10-31.json", "XAU/USD", D("3875.41047")),
    ],
)
def test_recorded_quotes_parse_exactly(fixture, symbol, close):
    q = provider({"/quote": fx(fixture)}).get_latest_quote(symbol)
    assert q.last_price == close
    assert q.bid is None and q.ask is None and q.mid is None  # no bid/ask on this plan
    assert q.observed_at == datetime(2026, 10, 31, 10, 27, tzinfo=UTC)  # last_quote_at
    assert q.provider_flags == {"is_market_open": "true"}  # recorded, never trusted


def test_bid_ask_used_when_provided():
    body = json.loads(fx("twelvedata_quote_usdils.recorded-2026-10-31.json"))
    body |= {"bid": "3.14150", "ask": "3.14160"}
    q = provider({"/quote": json.dumps(body)}).get_latest_quote("USD/ILS")
    assert q.mid == D("3.14155")


@pytest.mark.parametrize(
    "patch",
    [
        {"close": 3.14153},  # number instead of string
        {"close": "N/A"},  # non-numeric string
        {"close": "-1"},  # non-positive
        {"last_quote_at": "1793442420"},
        {"symbol": "EUR/USD"},  # wrong symbol returned
    ],
)
def test_contract_violations_rejected(patch):
    body = json.loads(fx("twelvedata_quote_usdils.recorded-2026-10-31.json")) | patch
    with pytest.raises(ProviderDataError):
        provider({"/quote": json.dumps(body)}).get_latest_quote("USD/ILS")


def test_missing_last_quote_at_rejected():
    body = json.loads(fx("twelvedata_quote_usdils.recorded-2026-10-31.json"))
    del body["last_quote_at"]
    with pytest.raises(ProviderDataError):
        provider({"/quote": json.dumps(body)}).get_latest_quote("USD/ILS")


def test_api_key_sent_in_header_never_in_url_or_logs(caplog):
    seen = []
    caplog.set_level(logging.DEBUG)
    provider(
        {"/quote": fx("twelvedata_quote_usdils.recorded-2026-10-31.json")}, seen
    ).get_latest_quote("USD/ILS")
    assert seen[0].headers["authorization"] == f"apikey {KEY}"
    assert KEY not in str(seen[0].url)
    assert KEY not in caplog.text


def test_error_bodies_mapped():
    with pytest.raises(ProviderRateLimited):
        provider({"/quote": fx("twelvedata_error_credits.json")}).get_latest_quote("USD/ILS")
    err = json.dumps({"code": 404, "message": "symbol not found", "status": "error"})
    with pytest.raises(ProviderRejected) as e:
        provider({"/quote": err}).get_latest_quote("USD/ILS")
    assert e.value.status_code == 404


def test_time_series_utc_parsing_and_params():
    seen = []
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    p = provider({"/time_series": fx("twelvedata_time_series_1min.json")}, seen, now)
    cs = p.get_intraday_ohlcv("USD/ILS", "1m", now - timedelta(hours=1), now)
    assert [c.open_time.minute for c in cs] == [57, 58, 59]
    assert cs[-1].close == D("3.14180") and cs[-1].volume is None and cs[-1].is_complete
    params = seen[0].url.params
    assert params["interval"] == "1min" and params["timezone"] == "UTC"
    assert params["start_date"] == "2026-11-04 11:00:00"


def test_time_series_rejects_non_utc_or_wrong_interval():
    body = json.loads(fx("twelvedata_time_series_1min.json"))
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    for meta in ({"exchange_timezone": "America/New_York"}, {"interval": "5min"}):
        bad = json.dumps(body | {"meta": body["meta"] | meta})
        with pytest.raises(ProviderDataError):
            provider({"/time_series": bad}, now=now).get_intraday_ohlcv(
                "USD/ILS", "1m", now - timedelta(hours=1), now
            )


def test_daily_and_4h_bars_never_taken_from_provider():
    p = provider({})
    for tf in ("1d", "4h"):
        with pytest.raises(CapabilityNotSupported):
            p.get_historical_ohlcv("USD/ILS", tf, RECEIVED - timedelta(days=5), RECEIVED)


def test_time_series_chunks_by_outputsize():
    seen = []
    empty = json.dumps(
        {
            "meta": {"symbol": "USD/ILS", "interval": "1min", "exchange_timezone": "UTC"},
            "values": [],
            "status": "ok",
        }
    )
    start = datetime(2026, 11, 1, tzinfo=UTC)
    provider({"/time_series": empty}, seen).get_historical_ohlcv(
        "USD/ILS", "1m", start, start + timedelta(minutes=12000)
    )
    assert len(seen) == 3  # 5000 + 5000 + 2000


def test_api_usage_status():
    st = provider({"/api_usage": fx("twelvedata_api_usage.json")}).get_provider_status()
    assert st.ok and st.detail == "credits used this minute: 3/8"


def test_missing_key_is_refused(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "twelvedata_api_key", None)
    with pytest.raises(ProviderRejected):
        TwelveDataProvider()
