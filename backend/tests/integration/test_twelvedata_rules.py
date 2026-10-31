"""Owner decisions 2026-10-31: session calendar authority, derived candles, BoI cross-check."""

import json
import pathlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest
from sqlalchemy import select

from app.ingestion import aggregate, crosscheck, service
from app.models import DataQualityEvent, MarketCandle, MarketQuote, OfficialReferenceRate
from app.providers.models import Candle
from app.providers.twelvedata import TwelveDataProvider

pytestmark = pytest.mark.integration
FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
SAT = datetime(2026, 10, 31, 10, 27, 30, tzinfo=UTC)


def td(fixture_text, now):
    return TwelveDataProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: now,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=fixture_text)),
    )


@pytest.mark.parametrize(
    "symbol,fixture",
    [
        ("USDILS", "twelvedata_quote_usdils.recorded-2026-10-31.json"),
        ("XAUUSD", "twelvedata_quote_xauusd.recorded-2026-10-31.json"),
    ],
)
def test_recorded_saturday_quote_is_suspect_out_of_session(db, symbol, fixture):
    r = service.ingest_quote(db, symbol, td((FIX / fixture).read_text(), SAT))
    assert r.ok and r.statuses == {"suspect": 1}
    row = db.scalar(select(MarketQuote))
    assert row.data_quality_status == "suspect" and row.last_price is not None
    assert row.mid is None  # no bid/ask -> last price only
    assert [i["type"] for i in row.quality_issues] == ["out_of_session"]
    ev = db.scalar(select(DataQualityEvent))
    assert ev.event_type == "out_of_session"
    assert ev.details_json == {"provider_is_market_open": "true"}  # kept for audit, not trusted
    # Excluded: freshness only considers verified quotes
    assert service.freshness(db, symbol, SAT).status == "no_data"


def test_same_quote_on_a_weekday_is_verified(db):
    body = json.loads((FIX / "twelvedata_quote_usdils.recorded-2026-10-31.json").read_text())
    wed = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    body["last_quote_at"] = int(wed.timestamp())
    r = service.ingest_quote(db, "USDILS", td(json.dumps(body), wed + timedelta(seconds=2)))
    assert r.statuses == {"verified": 1}
    f = service.freshness(db, "USDILS", wed + timedelta(seconds=30))
    assert f.status == "fresh" and f.provider == "twelvedata"


class FakeTD:
    name = "twelvedata"
    capabilities = frozenset()

    def __init__(self, candles):
        self.candles = candles

    def get_intraday_ohlcv(self, *a):
        return self.candles


def test_weekend_candle_is_suspect_out_of_session(db):
    t = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
    c = Candle(
        "USD/ILS",
        "1m",
        t,
        D("3.14"),
        D("3.15"),
        D("3.13"),
        D("3.14"),
        None,
        t + timedelta(minutes=2),
        True,
    )
    service.ingest_candles(
        db, "USDILS", FakeTD([c]), "1m", t, t + timedelta(minutes=1), detect_gaps=False
    )
    assert db.scalar(select(MarketCandle.data_quality_status)) == "suspect"


def test_provider_daily_and_4h_bars_are_never_ingested(db):
    for tf in ("1d", "4h"):
        with pytest.raises(ValueError, match="derived locally"):
            service.ingest_candles(db, "USDILS", FakeTD([]), tf, SAT - timedelta(days=2), SAT)


# ---------------------------------------------------------------- derived candles
def add_1h(db, symbol, provider, start, n, *, skip=(), base=D("3.0"), status="verified"):
    t = service.resolve(db, symbol, provider)
    for i in range(n):
        if i in skip:
            continue
        o = base + D(i) / 1000
        ot = start + timedelta(hours=i)
        db.add(
            MarketCandle(
                instrument_id=t.instrument.id,
                provider_id=t.provider.id,
                timeframe="1h",
                open_time=ot,
                close_time=ot + timedelta(hours=1),
                open=o,
                high=o + D("0.01"),
                low=o - D("0.01"),
                close=o + D("0.0005"),
                volume=None,
                is_complete=True,
                received_at=ot + timedelta(hours=1),
                data_quality_status=status,
            )
        )
    db.commit()


def derived(db, tf):
    return db.scalars(
        select(MarketCandle).where(MarketCandle.timeframe == tf).order_by(MarketCandle.open_time)
    ).all()


def test_daily_boundaries_follow_new_york_17h_across_dst(db):
    t = service.resolve(db, "USDILS", "twelvedata")
    b = aggregate.buckets(
        t, "1d", datetime(2026, 10, 29, tzinfo=UTC), datetime(2026, 11, 3, tzinfo=UTC)
    )
    opens = [o.strftime("%a %H:%M") for o, _ in b]
    # 17:00 New York = 21:00 UTC while EDT (until Sun 2026-11-01 02:00), 22:00 UTC after.
    # The first bucket overlapping Thu 00:00 UTC opens Wed 21:00 UTC.
    assert opens == ["Wed 21:00", "Thu 21:00", "Fri 21:00", "Sat 21:00", "Sun 22:00", "Mon 22:00"]
    assert b[3][1] - b[3][0] == timedelta(hours=25)  # Sat 17:00 EDT -> Sun 17:00 EST


def test_fx_daily_candle_built_from_24_verified_hours(db):
    day_open = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)  # Tue 17:00 EST
    add_1h(db, "USDILS", "twelvedata", day_open, 24)
    now = day_open + timedelta(days=1, minutes=5)
    r = aggregate.build_derived(
        db, "USDILS", "twelvedata", "1d", day_open, day_open + timedelta(hours=1), now
    )
    assert r.statuses == {"verified": 1}
    (c,) = derived(db, "1d")
    assert c.open_time == day_open and c.close_time == day_open + timedelta(days=1)
    # Hand-checked: open of hour 0, close of hour 23, max high, min low
    assert (c.open, c.high, c.low, c.close) == (D("3.0"), D("3.033"), D("2.99"), D("3.0235"))
    assert c.derived_from == "derived:1h"
    # Verified derived bars are immutable
    assert (
        aggregate.build_derived(
            db, "USDILS", "twelvedata", "1d", day_open, day_open + timedelta(hours=1), now
        ).skipped
        == 1
    )


def test_missing_hour_makes_daily_suspect_until_backfilled(db):
    day_open = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)
    add_1h(db, "USDILS", "twelvedata", day_open, 24, skip={5})
    now = day_open + timedelta(days=1, minutes=5)
    rng = (day_open, day_open + timedelta(hours=1), now)
    assert aggregate.build_derived(db, "USDILS", "twelvedata", "1d", *rng).statuses == {
        "suspect": 1
    }
    ev = db.scalar(
        select(DataQualityEvent).where(DataQualityEvent.event_type == "incomplete_source")
    )
    assert ev.details_json["missing"] == "1" and ev.details_json["expected"] == "24"
    add_1h(db, "USDILS", "twelvedata", day_open + timedelta(hours=5), 1, base=D("3.005"))
    assert aggregate.build_derived(db, "USDILS", "twelvedata", "1d", *rng).statuses == {
        "verified": 1
    }
    db.expire_all()
    assert derived(db, "1d")[0].data_quality_status == "verified"


def test_suspect_source_bars_are_excluded(db):
    day_open = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)
    add_1h(db, "USDILS", "twelvedata", day_open, 24, status="suspect")
    r = aggregate.build_derived(
        db,
        "USDILS",
        "twelvedata",
        "1d",
        day_open,
        day_open + timedelta(hours=1),
        day_open + timedelta(days=2),
    )
    assert r.stored == 0 and derived(db, "1d") == []


def test_gold_daily_break_hour_not_expected(db):
    day_open = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)  # 17:00 EST, break until 18:00
    add_1h(db, "XAUUSD", "twelvedata", day_open + timedelta(hours=1), 23, base=D("3900"))
    r = aggregate.build_derived(
        db,
        "XAUUSD",
        "twelvedata",
        "1d",
        day_open,
        day_open + timedelta(hours=1),
        day_open + timedelta(days=2),
    )
    assert r.statuses == {"verified": 1}


def test_unfinished_bucket_not_built(db):
    day_open = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)
    add_1h(db, "USDILS", "twelvedata", day_open, 10)
    r = aggregate.build_derived(
        db,
        "USDILS",
        "twelvedata",
        "1d",
        day_open,
        day_open + timedelta(hours=1),
        day_open + timedelta(hours=11),
    )
    assert r.stored == 0


def test_btc_4h_utc_buckets(db):
    start = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
    add_1h(db, "BTCUSD", "coinbase", start, 4, base=D("70000"))
    r = aggregate.build_derived(
        db,
        "BTCUSD",
        "coinbase",
        "4h",
        start,
        start + timedelta(hours=4),
        start + timedelta(hours=5),
    )
    assert r.statuses == {"verified": 1}
    (c,) = derived(db, "4h")
    assert (c.open_time, c.close) == (start, D("70000.0035"))


# ---------------------------------------------------------------- BoI cross-check
def add_ref(db, day, rate, published_at=None):
    t = service.resolve(db, "USDILS", "boi")
    db.add(
        OfficialReferenceRate(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            rate_date=day,
            rate=D(rate),
            published_at=published_at,
            received_at=datetime(2026, 11, 4, 14, tzinfo=UTC),
        )
    )
    db.commit()


def add_td_quote(db, at, last, status="verified"):
    t = service.resolve(db, "USDILS", "twelvedata")
    db.add(
        MarketQuote(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            observed_at=at,
            received_at=at,
            last_price=D(last),
            latency_ms=0,
            data_quality_status=status,
        )
    )
    db.commit()


DAY = date(2026, 11, 4)
PUB = datetime(2026, 11, 4, 13, 25, tzinfo=UTC)


def test_crosscheck_divergence_above_threshold_logged(db):
    add_ref(db, DAY, "3.719", PUB)
    add_td_quote(db, PUB - timedelta(minutes=5), "3.700")
    add_td_quote(db, PUB - timedelta(minutes=30), "3.719")  # outside the 15 min window
    r = crosscheck.crosscheck_boi(db, DAY, threshold_pct=D("0.5"), window_minutes=15)
    # |3.700 - 3.719| / 3.719 = 0.51089% (hand-checked) > 0.5%
    assert r.status == "diverged" and r.diff_pct == D("0.5109")
    assert r.market_source == "quote:last"
    ev = db.scalar(
        select(DataQualityEvent).where(DataQualityEvent.event_type == "reference_divergence")
    )
    assert D(ev.details_json["boi_rate"]) == D("3.719")
    assert ev.details_json["diff_pct"] == "0.5109"


def test_crosscheck_within_threshold_is_ok_and_silent(db):
    add_ref(db, DAY, "3.719", PUB)
    add_td_quote(db, PUB + timedelta(minutes=2), "3.720")
    r = crosscheck.crosscheck_boi(db, DAY, threshold_pct=D("0.5"), window_minutes=15)
    assert r.status == "ok" and r.diff_pct == D("0.0269")
    assert db.scalar(select(DataQualityEvent.id)) is None


def test_crosscheck_ignores_suspect_quotes_and_falls_back_to_candle(db):
    add_ref(db, DAY, "3.719", PUB)
    add_td_quote(db, PUB, "9.999", status="suspect")
    t = service.resolve(db, "USDILS", "twelvedata")
    ot = PUB - timedelta(minutes=1)
    db.add(
        MarketCandle(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            timeframe="1m",
            open_time=ot,
            close_time=PUB,
            open=D("3.718"),
            high=D("3.72"),
            low=D("3.717"),
            close=D("3.7185"),
            volume=None,
            is_complete=True,
            received_at=PUB,
            data_quality_status="verified",
        )
    )
    db.commit()
    r = crosscheck.crosscheck_boi(db, DAY, threshold_pct=D("0.5"), window_minutes=15)
    assert r.status == "ok" and r.market_source == "candle:1m_close"
    assert r.market_price == D("3.7185")


def test_crosscheck_without_data(db):
    assert crosscheck.crosscheck_boi(db, DAY).status == "no_reference"
    add_ref(db, DAY, "3.719")  # no published_at -> fallback 15:30 Asia/Jerusalem
    r = crosscheck.crosscheck_boi(db, DAY)
    assert r.status == "no_market_price"
    assert r.reference_time == datetime(2026, 11, 4, 13, 30, tzinfo=UTC)  # IST = UTC+2


# ---------------------------------------------------------------- API + tasks
def test_quote_api_shows_weekend_quote_as_excluded(client, db):
    from tests.integration.conftest import login, make_user

    r = service.ingest_quote(
        db,
        "USDILS",
        td((FIX / "twelvedata_quote_usdils.recorded-2026-10-31.json").read_text(), SAT),
    )
    assert r.ok, r.error
    make_user(db, role="viewer")
    login(client)
    body = client.get("/api/v1/markets/USDILS/quote").json()
    assert body["provider"] == "twelvedata"
    assert body["mid"] is None and body["last_price"] is None  # no verified quote
    assert body["signals_allowed"] is False
    ex = body["latest_excluded"]
    assert ex["price"] == "3.1415300000" and ex["price_type"] == "last"
    assert ex["reasons"] == ["out_of_session"] and ex["data_quality_status"] == "suspect"
    assert ex["observed_at"].startswith("2026-10-31T10:27:00")


def test_crosscheck_task_retries_recent_dates_without_price(db, monkeypatch):
    from app.tasks import ingestion as tasks

    monkeypatch.setattr(tasks, "utcnow", lambda: datetime(2026, 11, 5, 9, tzinfo=UTC))
    add_ref(db, date(2026, 11, 4), "3.719", PUB)  # yesterday, no Twelve Data price yet
    add_ref(db, date(2026, 11, 3), "3.722")  # 2 days ago: give up, record status
    out = tasks.boi_crosscheck.run(days=3)
    assert out.split(",") == ["succeeded", "retry", "succeeded"]  # 11-05 has no ref -> ok
    add_td_quote(db, PUB, "3.720")
    assert tasks.boi_crosscheck.run(days=3).split(",") == ["skipped", "succeeded", "skipped"]
