import json
import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest

from app.providers.coinbase import CoinbaseExchangeProvider
from app.providers.errors import CapabilityNotSupported, ProviderDataError
from app.providers.models import Capability

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
NOW = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)


def provider(routes, requests=None, now=NOW):
    def handler(req: httpx.Request):
        if requests is not None:
            requests.append(req)
        for prefix, body in routes.items():
            if req.url.path == prefix:
                return httpx.Response(200, text=body if isinstance(body, str) else json.dumps(body))
        return httpx.Response(404)

    return CoinbaseExchangeProvider(
        transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: now
    )


def fx(name):
    return (FIX / name).read_text()


def test_latest_quote_parsed_as_decimals():
    q = provider({"/products/BTC-USD/ticker": fx("coinbase_ticker.json")}).get_latest_quote(
        "BTC-USD"
    )
    assert q.bid == D("70009.88") and q.ask == D("70010.12") and q.last_price == D("70010.00")
    assert q.mid == D("70010.00")
    assert q.observed_at == datetime(2026, 11, 4, 11, 59, 58, 123456, tzinfo=UTC)
    assert q.received_at == NOW and q.latency_ms == 1876


def test_candles_sorted_complete_flag_and_exact_decimals():
    reqs = []
    p = provider({"/products/BTC-USD/candles": fx("coinbase_candles.json")}, reqs)
    start = datetime(2026, 11, 4, 11, 0, tzinfo=UTC)
    cs = p.get_intraday_ohlcv("BTC-USD", "1m", start, start + timedelta(hours=1))
    assert [c.open_time.minute for c in cs] == [41, 42, 43]  # ascending
    last = cs[-1]
    assert (last.open, last.high, last.low, last.close) == (
        D("70000.0"),
        D("70012.25"),
        D("69990.5"),
        D("70010.0"),
    )
    assert last.volume == D("3.51234")  # no float rounding
    assert all(c.is_complete for c in cs)  # 11:43 + 1m <= 12:00
    assert reqs[0].url.params["granularity"] == "60"


def test_candles_paginate_by_300_buckets():
    reqs = []
    p = provider({"/products/BTC-USD/candles": "[]"}, reqs)
    start = datetime(2026, 11, 1, tzinfo=UTC)
    p.get_historical_ohlcv("BTC-USD", "1m", start, start + timedelta(minutes=700))
    assert len(reqs) == 3  # 300 + 300 + 100


def test_current_bucket_marked_incomplete():
    bucket = datetime(2026, 11, 4, 11, 59, tzinfo=UTC)
    row = [[int(bucket.timestamp()), 1, 2, 1, 2, 1]]
    mid_bucket = bucket + timedelta(seconds=30)
    p = provider({"/products/BTC-USD/candles": json.dumps(row)}, now=mid_bucket)
    (c,) = p.get_intraday_ohlcv("BTC-USD", "1m", bucket - timedelta(minutes=5), NOW)
    assert c.open_time == bucket and not c.is_complete


def test_4h_not_offered():
    with pytest.raises(CapabilityNotSupported):
        provider({}).get_intraday_ohlcv("BTC-USD", "4h", NOW - timedelta(days=1), NOW)


@pytest.mark.parametrize(
    "body",
    [
        "[[1793792580, 1, 2, 1, 2]]",  # 5 fields
        '[["1793792580", 1, 2, 1, 2, 1]]',  # time as string
        "[[1793792580, 1, 2, 1, -2, 1]]",  # negative price
        '{"message": "oops"}',  # not an array
        "not json",
    ],
)
def test_malformed_candles_raise_data_error(body):
    with pytest.raises(ProviderDataError):
        provider({"/products/BTC-USD/candles": body}).get_intraday_ohlcv(
            "BTC-USD", "1m", NOW - timedelta(minutes=5), NOW
        )


def test_ticker_missing_field_raises():
    with pytest.raises(ProviderDataError):
        provider({"/products/BTC-USD/ticker": '{"price": "1"}'}).get_latest_quote("BTC-USD")


def test_order_book_market_and_provider_status():
    p = provider(
        {
            "/products/BTC-USD/book": fx("coinbase_book.json"),
            "/products/BTC-USD": fx("coinbase_product.json"),
            "/time": fx("coinbase_time.json"),
        }
    )
    book = p.get_order_book("BTC-USD", depth=1)
    assert book.bids[0].price == D("70009.88") and len(book.asks) == 1
    assert p.get_market_status("BTC-USD").status == "open"
    st = p.get_provider_status()
    assert st.ok and st.server_time == datetime(2026, 11, 4, 12, 0, 0, 250000, tzinfo=UTC)


def test_disabled_product_is_halted():
    prod = json.loads(fx("coinbase_product.json")) | {"trading_disabled": True}
    p = provider({"/products/BTC-USD": prod})
    assert p.get_market_status("BTC-USD").status == "halted"


def test_capabilities_declared_and_reference_rates_unsupported():
    p = provider({})
    assert p.supports(Capability.LATEST_QUOTE) and not p.supports(Capability.REFERENCE_RATE)
    with pytest.raises(CapabilityNotSupported):
        p.get_reference_rates("USD", NOW.date(), NOW.date())
