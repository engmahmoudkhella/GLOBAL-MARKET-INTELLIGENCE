import json
import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest

from app.providers.binance import BinanceProvider
from app.providers.coingecko import CoinGeckoProvider
from app.providers.errors import CapabilityNotSupported, ProviderDataError, ProviderRejected

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
NOW = datetime(2026, 10, 31, 11, 0, 30, tzinfo=UTC)


def fx(n):
    return (FIX / n).read_text()


def routed(routes, seen=None):
    def h(r):
        if seen is not None:
            seen.append(r)
        if r.url.path in routes:
            body = routes[r.url.path]
            return (
                httpx.Response(body[0], text=body[1])
                if isinstance(body, tuple)
                else httpx.Response(200, text=body)
            )
        return httpx.Response(404)

    return httpx.MockTransport(h)


# ---------------- CoinGecko (doc-derived fixtures) ----------------
def cg(routes, seen=None):
    return CoinGeckoProvider(
        api_key="cg-key", transport=routed(routes, seen), sleep=lambda s: None, clock=lambda: NOW
    )


def test_coingecko_quote_exact_decimal_and_header_key():
    seen = []
    q = cg({"/api/v3/simple/price": fx("coingecko_simple_price.json")}, seen).get_latest_quote(
        "bitcoin"
    )
    assert q.last_price == D("77281.12345") and q.bid is None and q.mid is None
    assert q.observed_at == datetime(2026, 10, 31, 10, 37, tzinfo=UTC)
    assert seen[0].headers["x-cg-demo-api-key"] == "cg-key"
    assert "cg-key" not in str(seen[0].url)
    assert seen[0].url.params["vs_currencies"] == "usd"


@pytest.mark.parametrize(
    "body",
    [
        '{"bitcoin":{"usd":"77281.1","last_updated_at":1793443020}}',  # string
        '{"bitcoin":{"eur":70000,"last_updated_at":1793443020}}',  # no usd
        '{"bitcoin":{"usd":77281.1}}',  # no timestamp
        "{}",
    ],
)
def test_coingecko_contract_violations(body):
    with pytest.raises(ProviderDataError):
        cg({"/api/v3/simple/price": body}).get_latest_quote("bitcoin")


def test_coingecko_ping_and_missing_key(monkeypatch):
    assert cg({"/api/v3/ping": fx("coingecko_ping.json")}).get_provider_status().ok
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "coingecko_demo_api_key", None)
    with pytest.raises(ProviderRejected):
        CoinGeckoProvider()


# ---------------- Binance (doc-derived fixtures) ----------------
def bn(routes, seen=None, now=NOW):
    return BinanceProvider(transport=routed(routes, seen), sleep=lambda s: None, clock=lambda: now)


def test_binance_book_ticker_mid_and_observed_at_source_flag():
    seen = []
    q = bn({"/api/v3/ticker/bookTicker": fx("binance_book_ticker.json")}, seen).get_latest_quote(
        "BTCUSDT"
    )
    assert q.mid == D("77290.015") and q.observed_at == NOW
    assert q.provider_flags == {"observed_at_source": "received"}  # no provider timestamp
    assert seen[0].url.host == "data-api.binance.vision"


def test_binance_symbol_mismatch_rejected():
    body = fx("binance_book_ticker.json").replace("BTCUSDT", "BTCUSDC")
    with pytest.raises(ProviderDataError):
        bn({"/api/v3/ticker/bookTicker": body}).get_latest_quote("BTCUSDT")


def test_binance_klines_explicit_columns_and_completeness():
    seen = []
    now = datetime(2026, 10, 31, 10, 0, 30, tzinfo=UTC)
    cs = bn({"/api/v3/klines": fx("binance_klines_1m.json")}, seen, now).get_intraday_ohlcv(
        "BTCUSDT", "1m", now - timedelta(minutes=10), now + timedelta(minutes=1)
    )
    assert [c.open_time.strftime("%H:%M") for c in cs] == ["09:58", "09:59", "10:00"]
    c0 = cs[0]
    assert (c0.open, c0.high, c0.low, c0.close, c0.volume) == (
        D("77300"),
        D("77310"),
        D("77295.5"),
        D("77305.25"),
        D("12.345"),
    )
    assert [c.is_complete for c in cs] == [True, True, False]
    assert seen[0].url.params["interval"] == "1m" and seen[0].url.params["limit"] == "1000"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.__setitem__(6, r[6] + 1),  # closeTime inconsistent with 1m
        lambda r: r.__setitem__(3, "77400.0"),  # low above open/close
        lambda r: r.__setitem__(1, 77300.0),  # number where string expected
    ],
)
def test_binance_bad_klines_rejected(mutate):
    rows = json.loads(fx("binance_klines_1m.json"))
    mutate(rows[0])
    with pytest.raises(ProviderDataError):
        bn({"/api/v3/klines": json.dumps(rows)}).get_intraday_ohlcv(
            "BTCUSDT", "1m", NOW - timedelta(hours=2), NOW
        )


def test_binance_geo_block_is_rejected_not_retried():
    seen = []
    with pytest.raises(ProviderRejected) as e:
        bn(
            {"/api/v3/ticker/bookTicker": (451, '{"code":0,"msg":"restricted location"}')}, seen
        ).get_latest_quote("BTCUSDT")
    assert e.value.status_code == 451 and len(seen) == 1


def test_binance_derived_timeframes_not_fetched():
    with pytest.raises(CapabilityNotSupported):
        bn({}).get_historical_ohlcv("BTCUSDT", "1d", NOW - timedelta(days=3), NOW)


def test_binance_server_time():
    st = bn({"/api/v3/time": fx("binance_time.json")}).get_provider_status()
    assert st.server_time == datetime(2026, 10, 31, 10, 37, 0, 123000, tzinfo=UTC)
