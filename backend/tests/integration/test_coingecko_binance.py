import pathlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest
from sqlalchemy import select

from app.ingestion import crosscheck, service
from app.models import DataQualityEvent, Instrument, MarketCandle, MarketQuote
from app.providers.binance import BinanceProvider
from app.providers.coingecko import CoinGeckoProvider

pytestmark = pytest.mark.integration
FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
CG_AT = datetime(2026, 10, 31, 10, 37, tzinfo=UTC)  # last_updated_at in the fixture


def cg_adapter(body=None):
    text = body or (FIX / "coingecko_simple_price.json").read_text()
    return CoinGeckoProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: CG_AT + timedelta(seconds=20),
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=text)),
    )


def add_coinbase_quote(db, at, bid, ask):
    t = service.resolve(db, "BTCUSD", "coinbase")
    db.add(
        MarketQuote(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            observed_at=at,
            received_at=at,
            bid=D(bid),
            ask=D(ask),
            mid=(D(bid) + D(ask)) / 2,
            latency_ms=0,
            data_quality_status="verified",
        )
    )
    db.commit()


def test_coingecko_reference_stored_but_not_primary(db):
    r = service.ingest_quote(db, "BTCUSD", cg_adapter())
    assert r.statuses == {"verified": 1}
    # Freshness/price of BTCUSD come only from the primary (Coinbase): still no data
    assert service.freshness(db, "BTCUSD", CG_AT).status == "no_data"


def test_coingecko_vs_coinbase_within_threshold(db):
    add_coinbase_quote(db, CG_AT - timedelta(seconds=30), "77290.00", "77290.02")
    service.ingest_quote(db, "BTCUSD", cg_adapter())
    r = crosscheck.crosscheck_reference_quote(db, "BTCUSD", "coingecko")
    # |77281.12345 - 77290.01| / 77290.01 = 0.0115% (hand-checked)
    assert r.status == "ok" and r.diff_pct == D("0.0115")
    assert db.scalar(select(DataQualityEvent.id)) is None


def test_coingecko_vs_coinbase_divergence_logged(db):
    add_coinbase_quote(db, CG_AT + timedelta(seconds=10), "78000.00", "78000.00")
    add_coinbase_quote(db, CG_AT - timedelta(minutes=10), "77281.00", "77281.00")  # outside 2m
    service.ingest_quote(db, "BTCUSD", cg_adapter())
    r = crosscheck.crosscheck_reference_quote(db, "BTCUSD", "coingecko")
    # |77281.12345 - 78000| / 78000 = 0.9216% > 0.5%
    assert r.status == "diverged" and r.diff_pct == D("0.9216")
    ev = db.scalar(
        select(DataQualityEvent).where(DataQualityEvent.event_type == "reference_divergence")
    )
    assert ev.details_json["reference_provider"] == "coingecko"


def test_coingecko_without_primary_price(db):
    service.ingest_quote(db, "BTCUSD", cg_adapter())
    assert (
        crosscheck.crosscheck_reference_quote(db, "BTCUSD", "coingecko").status
        == "no_primary_price"
    )


def test_binance_lands_only_under_btcusdt(db):
    now = datetime(2026, 10, 31, 10, 0, 30, tzinfo=UTC)
    routes = {
        "/api/v3/ticker/bookTicker": (FIX / "binance_book_ticker.json").read_text(),
        "/api/v3/klines": (FIX / "binance_klines_1m.json").read_text(),
    }
    adapter = BinanceProvider(
        sleep=lambda s: None,
        clock=lambda: now,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=routes[r.url.path])),
    )
    assert service.ingest_quote(db, "BTCUSDT", adapter).statuses == {"verified": 1}
    r = service.ingest_candles(
        db,
        "BTCUSDT",
        adapter,
        "1m",
        now - timedelta(minutes=10),
        now + timedelta(minutes=1),
        detect_gaps=False,
    )
    assert r.stored == 2 and r.dropped_incomplete == 1
    usdt = db.scalar(select(Instrument.id).where(Instrument.symbol == "BTCUSDT"))
    assert set(db.scalars(select(MarketQuote.instrument_id))) == {usdt}
    assert set(db.scalars(select(MarketCandle.instrument_id))) == {usdt}
    assert service.freshness(db, "BTCUSDT", now + timedelta(seconds=30)).status == "fresh"
    with pytest.raises(LookupError):
        service.ingest_quote(db, "BTCUSD", adapter)  # binance is not mapped to BTCUSD
