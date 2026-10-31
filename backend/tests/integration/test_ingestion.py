import json
import pathlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest
from sqlalchemy import select, text

from app.ingestion import service
from app.models import DataQualityEvent, MarketCandle, MarketProvider, MarketQuote
from app.models import OfficialReferenceRate as Ref
from app.providers.base import MarketDataProvider
from app.providers.coinbase import CoinbaseExchangeProvider
from app.providers.errors import ProviderUnavailable
from app.providers.models import Candle, Capability, Quote, ReferenceRate

pytestmark = pytest.mark.integration
FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class FakeCoinbase(MarketDataProvider):
    """Test double registered under the coinbase name (DEVELOPMENT FIXTURE)."""

    name = "coinbase"
    capabilities = frozenset({Capability.LATEST_QUOTE, Capability.INTRADAY_OHLCV})

    def __init__(self):
        self.quotes, self.candles, self.fail = [], [], 0

    def get_latest_quote(self, s):
        if self.fail:
            self.fail -= 1
            raise ProviderUnavailable("coinbase", "simulated outage")
        return self.quotes.pop(0)

    def get_intraday_ohlcv(self, s, tf, start, end):
        return list(self.candles)


class FakeBoi(MarketDataProvider):
    name = "boi"
    capabilities = frozenset({Capability.REFERENCE_RATE})

    def __init__(self, rates):
        self.rates = rates

    def get_reference_rates(self, s, start, end):
        return list(self.rates)


def q(t, bid="70000", ask="70001", last="70000.5"):
    return Quote(
        "BTC-USD",
        t,
        t + timedelta(milliseconds=300),
        D(bid) if bid else None,
        D(ask) if ask else None,
        D(last) if last else None,
    )


def c(t, o="100", h="101", lo="99", cl="100.5", complete=True):
    return Candle(
        "BTC-USD",
        "1m",
        t,
        D(o),
        D(h),
        D(lo),
        D(cl),
        D("1"),
        t + timedelta(minutes=1, seconds=1),
        complete,
    )


def provider_row(db, name="coinbase"):
    db.expire_all()
    return db.scalar(select(MarketProvider).where(MarketProvider.provider_name == name))


def test_quote_stored_with_source_timestamps_and_idempotent(db):
    fake = FakeCoinbase()
    fake.quotes = [q(T0), q(T0)]
    r = service.ingest_quote(db, "BTCUSD", fake)
    assert r.ok and r.stored == 1 and r.statuses == {"verified": 1}
    row = db.scalar(select(MarketQuote))
    assert row.provider_id == provider_row(db).id
    assert row.observed_at == T0 and row.received_at == T0 + timedelta(milliseconds=300)
    assert row.mid == D("70000.5") and row.latency_ms == 300
    assert service.ingest_quote(db, "BTCUSD", fake).skipped == 1  # same observation
    p = provider_row(db)
    assert p.status == "active" and p.capabilities == ["intraday_ohlcv", "latest_quote"]


def test_crossed_quote_rejected_and_event_recorded(db):
    fake = FakeCoinbase()
    fake.quotes = [q(T0, bid="70002", ask="70001")]
    r = service.ingest_quote(db, "BTCUSD", fake)
    assert r.statuses == {"rejected": 1}
    assert db.scalar(select(MarketQuote.data_quality_status)) == "rejected"
    ev = db.scalar(select(DataQualityEvent))
    assert ev.event_type == "crossed_quote" and ev.severity == "reject"


def test_provider_outage_degrades_then_down_then_recovers(db):
    fake = FakeCoinbase()
    fake.fail = 5
    for i in range(5):
        r = service.ingest_quote(db, "BTCUSD", fake)  # never raises
        assert not r.ok and "simulated outage" in r.error
        assert provider_row(db).status == ("down" if i == 4 else "degraded")
    outages = db.scalars(
        select(DataQualityEvent).where(DataQualityEvent.event_type == "outage")
    ).all()
    assert len(outages) == 1
    fake.quotes = [q(T0)]
    assert service.ingest_quote(db, "BTCUSD", fake).ok
    p = provider_row(db)
    assert p.status == "active" and p.consecutive_failures == 0
    assert db.scalar(select(MarketQuote.observed_at)) == T0  # nothing stored while down


def test_incomplete_candle_replaced_but_completed_candle_immutable(db):
    fake = FakeCoinbase()
    fake.candles = [c(T0, cl="100.2", complete=False)]
    kw = dict(start=T0, end=T0 + timedelta(minutes=1), detect_gaps=False)
    service.ingest_candles(db, "BTCUSD", fake, "1m", **kw)
    fake.candles = [c(T0, cl="100.5", complete=True)]
    assert service.ingest_candles(db, "BTCUSD", fake, "1m", **kw).stored == 1
    fake.candles = [c(T0, cl="999", h="1000", complete=True)]  # late revision attempt
    assert service.ingest_candles(db, "BTCUSD", fake, "1m", **kw).skipped == 1
    db.expire_all()
    row = db.scalar(select(MarketCandle))
    assert row.close == D("100.5") and row.is_complete


def test_invalid_candle_rejected_and_flagged(db):
    fake = FakeCoinbase()
    fake.candles = [c(T0, h="99")]
    r = service.ingest_candles(
        db, "BTCUSD", fake, "1m", T0, T0 + timedelta(minutes=1), detect_gaps=False
    )
    assert r.statuses == {"rejected": 1}
    assert db.scalar(select(DataQualityEvent.event_type)) == "invalid_ohlc"


def test_gap_detection_records_each_gap_once(db):
    fake = FakeCoinbase()
    fake.candles = [c(T0 + timedelta(minutes=i)) for i in range(10) if i not in (4, 5)]
    end = T0 + timedelta(minutes=10)
    service.ingest_candles(db, "BTCUSD", fake, "1m", T0, end, detect_gaps=False)
    t = service.resolve(db, "BTCUSD", "coinbase")
    assert service.record_gaps(db, t, "1m", T0, end) == 1
    db.commit()
    assert service.record_gaps(db, t, "1m", T0, end) == 0  # not duplicated
    db.commit()
    ev = db.scalar(select(DataQualityEvent).where(DataQualityEvent.event_type == "missing_candle"))
    assert ev.window_start == T0 + timedelta(minutes=4)
    assert ev.window_end == T0 + timedelta(minutes=6)
    assert ev.details_json["count"] == "2" and ev.details_json["timeframe"] == "1m"


def test_reference_rates_stored_and_never_silently_revised(db):
    now = T0
    boi = FakeBoi([ReferenceRate("USD", date(2026, 11, 3), D("3.719"), now)])
    r = service.ingest_reference_rates(db, "USDILS", boi, date(2026, 11, 1), date(2026, 11, 4))
    assert r.ok and r.stored == 1
    assert (
        service.ingest_reference_rates(
            db, "USDILS", boi, date(2026, 11, 1), date(2026, 11, 4)
        ).skipped
        == 1
    )
    boi.rates = [ReferenceRate("USD", date(2026, 11, 3), D("3.800"), now)]
    r = service.ingest_reference_rates(db, "USDILS", boi, date(2026, 11, 1), date(2026, 11, 4))
    assert r.issues == 1
    db.expire_all()
    assert db.scalar(select(Ref.rate)) == D("3.719")
    # Reference rates never appear as market quotes
    assert db.execute(text("SELECT count(*) FROM market_quotes")).scalar() == 0


def test_freshness_states_and_stale_event_dedup(db):
    assert service.freshness(db, "BTCUSD", T0).status == "no_data"
    fake = FakeCoinbase()
    fake.quotes = [q(T0)]
    service.ingest_quote(db, "BTCUSD", fake)
    assert service.freshness(db, "BTCUSD", T0 + timedelta(seconds=60)).status == "fresh"
    later = T0 + timedelta(seconds=121)  # BTCUSD staleness_seconds = 120
    assert service.record_staleness(db, "BTCUSD", later).status == "stale"
    service.record_staleness(db, "BTCUSD", later + timedelta(minutes=5))
    stale = db.scalars(select(DataQualityEvent).where(DataQualityEvent.event_type == "stale"))
    assert len(stale.all()) == 1
    # USDILS on a Saturday with no data: still no_data; with old data: market_closed
    assert (
        service.freshness(db, "USDILS", datetime(2026, 11, 7, 12, tzinfo=UTC)).status == "no_data"
    )


def test_end_to_end_coinbase_adapter_with_fixtures(db):
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

    def handler(req):
        name = {
            "/products/BTC-USD/ticker": "coinbase_ticker.json",
            "/products/BTC-USD/candles": "coinbase_candles.json",
        }.get(req.url.path)
        return httpx.Response(200, text=(FIX / name).read_text()) if name else httpx.Response(404)

    adapter = CoinbaseExchangeProvider(
        transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: now
    )
    assert service.ingest_quote(db, "BTCUSD", adapter).stored == 1
    r = service.ingest_candles(
        db, "BTCUSD", adapter, "1m", now - timedelta(hours=1), now, detect_gaps=False
    )
    assert r.stored == 3 and r.statuses == {"verified": 3}
    rows = db.execute(text("SELECT instrument_id, close FROM market_candles ORDER BY open_time"))
    closes = [row.close for row in rows]
    assert closes == [D("69985.5"), D("70000.0"), D("70010.0")]


def test_btcusdt_cannot_be_ingested_through_coinbase(db):
    with pytest.raises(LookupError):
        service.resolve(db, "BTCUSDT", "coinbase")
    with pytest.raises(LookupError):
        service.resolve(db, "BTCUSD", "binance")


def test_compression_and_retention_policies_installed(db):
    jobs = db.execute(
        text(
            "SELECT hypertable_name, proc_name, config::text FROM timescaledb_information.jobs "
            "WHERE hypertable_name IN ('market_quotes','market_candles') ORDER BY 1, 2"
        )
    ).all()
    summary = {(j.hypertable_name, j.proc_name): json.loads(j.config) for j in jobs}
    assert summary[("market_candles", "policy_compression")]["compress_after"] == "2 years"
    assert ("market_candles", "policy_retention") not in summary  # never auto-deleted (D7)
    assert summary[("market_quotes", "policy_retention")]["drop_after"] == "90 days"
