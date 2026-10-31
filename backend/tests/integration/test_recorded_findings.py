"""Owner's live recordings 2026-10-31: findings A, B, C, G, H and holiday calendars."""

import pathlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest
from sqlalchemy import select, text

from app.ingestion import crosscheck, service
from app.markets.calendars import boi_publication_days
from app.markets.holidays import israeli_rest_days, yom_haatzmaut
from app.models import DataQualityEvent, MarketCandle, MarketHoliday, OfficialReferenceRate
from app.providers.boi import BankOfIsraelProvider
from app.providers.coinbase import CoinbaseExchangeProvider
from app.providers.twelvedata import TwelveDataProvider
from tests.unit.test_recorded_findings import TD_RECEIVED, utc_shifted_series

pytestmark = pytest.mark.integration
FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "providers"
NOW = datetime(2026, 10, 31, 10, 56, 27, tzinfo=UTC)


def boi_adapter():
    json_text = (FIX / "boi_exchange_rates.recorded-2026-10-31.json").read_text()
    xml_text = (FIX / "boi_sdmx_rer_usd_ils.browser-copy-2026-10-31.xml").read_text()

    def handler(r):
        return httpx.Response(200, text=json_text if r.url.host == "www.boi.org.il" else xml_text)

    return BankOfIsraelProvider(
        transport=httpx.MockTransport(handler), sleep=lambda s: None, clock=lambda: NOW
    )


# --- B + C: exact recorded series ----------------------------------------------------------
def test_recorded_boi_series_27_oct_is_special_closure_not_a_gap(db):
    """27 Oct 2026 = Knesset election day (special_closures seed): no missing_reference."""
    r = service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
    )
    assert r.ok and r.stored == 8
    assert (
        db.scalars(
            select(DataQualityEvent).where(DataQualityEvent.event_type == "missing_reference")
        ).all()
        == []
    )
    assert (
        db.scalar(
            select(OfficialReferenceRate).where(
                OfficialReferenceRate.rate_date == date(2026, 10, 27)
            )
        )
        is None
    )  # never filled


def test_without_the_special_closure_27_oct_is_a_gap_then_explained(db):
    db.execute(text("DELETE FROM special_closures WHERE closure_date = '2026-10-27'"))
    db.commit()
    try:
        service.ingest_reference_rates(
            db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
        )
        (ev,) = db.scalars(
            select(DataQualityEvent).where(DataQualityEvent.event_type == "missing_reference")
        ).all()
        assert ev.details_json["rate_date"] == "2026-10-27" and ev.explanation_status is None
    finally:
        db.execute(
            text(
                "INSERT INTO special_closures (calendar, closure_date, reason, source_url) VALUES "
                "('boi', '2026-10-27', 'Knesset election day - statutory day off (Basic Law: The "
                "Knesset, section 10)', 'https://www.shibolet.com/?p=27864')"
            )
        )
        db.commit()
    # Next ingestion: the event is kept and explained, no new event is raised
    service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
    )
    db.expire_all()
    (ev,) = db.scalars(
        select(DataQualityEvent).where(DataQualityEvent.event_type == "missing_reference")
    ).all()
    assert ev.explanation_status == "explained"
    assert ev.explanation.startswith("holiday: Knesset election day")
    assert ev.explained_at is not None and ev.details_json["rate_date"] == "2026-10-27"


def test_migration_reclassification_sql_explains_existing_event(db):
    import importlib

    mig = importlib.import_module("migrations.versions.0006_special_closures")
    t = service.resolve(db, "USDILS", "boi")
    db.add(
        DataQualityEvent(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            event_type="missing_reference",
            severity="suspect",
            message="no BoI representative rate for business day 2026-10-27",
            detected_at=NOW,
            details_json={"rate_date": "2026-10-27"},
        )
    )
    db.commit()
    db.execute(text(mig.EXPLAIN_SQL))
    db.commit()
    ev = db.scalar(select(DataQualityEvent))
    assert ev.explanation_status == "explained" and "Knesset" in ev.explanation


def test_special_closure_seed_and_source_required(db):
    from app.models import SpecialClosure

    (sc,) = db.scalars(select(SpecialClosure)).all()
    assert (sc.calendar, sc.closure_date.isoformat()) == ("boi", "2026-10-27")
    assert sc.source_url == "https://www.shibolet.com/?p=27864"
    with pytest.raises(Exception):  # noqa: B017 - CHECK constraint on source_url
        db.execute(
            text(
                "INSERT INTO special_closures (calendar, closure_date, reason, "
                "source_url) VALUES ('boi', '2027-01-05', 'x', 'not a url')"
            )
        )
    db.rollback()


def test_boi_publication_observations_and_stats(db):
    from app.ingestion.boi_stats import publication_stats

    service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
    )
    db.commit()
    st = publication_stats(db)
    # One observed lastUpdate (30 Oct 12:21:03 IST): far below 20 business days
    assert st.business_days == 1 and not st.sufficient
    assert st.median_local == "12:21:04" and st.configured_fallback == "12:30:00"


def test_publication_stats_median_and_range_hand_checked(db):
    from app.ingestion.boi_stats import publication_stats
    from app.models import BoiPublicationObservation

    # 20 business days: 12:10, 12:11, ... 12:29 Israel time (IST, UTC+2) in Nov 2026
    days = [
        d for d in (date(2026, 11, 2) + timedelta(days=i) for i in range(28)) if d.weekday() < 5
    ][:20]
    for i, d in enumerate(days):
        at = datetime(d.year, d.month, d.day, 10, 10 + i, tzinfo=UTC)
        db.add(BoiPublicationObservation(rate_date=d, published_at=at, first_observed_at=at))
        # a later re-observation of the same date must not count twice
        db.add(
            BoiPublicationObservation(
                rate_date=d,
                published_at=at + timedelta(hours=3),
                first_observed_at=at + timedelta(hours=3),
            )
        )
    db.commit()
    st = publication_stats(db)
    assert st.business_days == 20 and st.sufficient
    # median of 12:10..12:29 = (12:19 + 12:20) / 2 = 12:19:30
    assert (st.median_local, st.earliest_local, st.latest_local) == (
        "12:19:30",
        "12:10:00",
        "12:29:00",
    )
    assert st.configured_fallback == "12:30:00"  # never changed automatically


def test_good_friday_is_reduced_liquidity_not_a_closure(db):
    t = service.resolve(db, "XAUUSD", "twelvedata")
    gf = datetime(2027, 3, 26, 14, 0, tzinfo=UTC)
    assert t.calendar.is_open(gf)  # not a hard closure
    assert [w.name for w in t.reduced_liquidity if w.start <= gf < w.end] == ["Good Friday"]
    assert service.record_gaps(db, t, "1h", gf, gf + timedelta(hours=2)) == 1
    db.commit()
    ev = db.scalar(select(DataQualityEvent).where(DataQualityEvent.event_type == "missing_candle"))
    assert ev.details_json["reduced_liquidity_day"] == "Good Friday"
    usd = service.resolve(db, "USDILS", "twelvedata")  # FX calendar unaffected
    assert usd.reduced_liquidity == ()


def test_raw_attributes_stored_and_merged(db):
    service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
    )
    db.expire_all()
    oct30 = db.scalar(
        select(OfficialReferenceRate).where(OfficialReferenceRate.rate_date == date(2026, 10, 30))
    )
    assert oct30.rate == D("3.118")
    a = oct30.attributes_json
    assert a["obs.RELEASE_STATUS"] == "YP" and a["series.TIME_COLLECT"] == "V"
    # The same day also came from PublicApi: its timestamp and raw fields are merged in
    assert oct30.published_at == datetime(2026, 10, 30, 10, 21, 3, 773145, tzinfo=UTC)
    assert a["current_change_pct"] == "0.12845215157353885677585100" and a["unit"] == "1"


def test_boi_publication_calendar_weekdays_minus_holidays(db):
    days = boi_publication_days(db, date(2026, 10, 19), date(2026, 10, 25))
    assert [d.strftime("%a") for d in days] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    # Yom Kippur 2026 (Mon 21 Sep) is a seeded 'boi' closure (assumption)
    assert date(2026, 9, 21) not in boi_publication_days(db, date(2026, 9, 21), date(2026, 9, 21))


# --- A: publication time and cross-check window ---------------------------------------------
def test_crosscheck_uses_lastupdate_when_present(db):
    service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30)
    )
    r = crosscheck.crosscheck_boi(db, date(2026, 10, 30))
    assert r.reference_time == datetime(2026, 10, 30, 10, 21, 3, 773145, tzinfo=UTC)


def test_fallback_publication_time_is_12_30_israel_in_both_seasons(db):
    service.ingest_reference_rates(
        db, "USDILS", boi_adapter(), date(2026, 10, 20), date(2026, 10, 30), include_latest=False
    )
    # 20 Oct: IDT (UTC+3) -> 09:30 UTC; 26 Oct: IST (UTC+2, after 25 Oct) -> 10:30 UTC
    assert crosscheck.crosscheck_boi(db, date(2026, 10, 20)).reference_time == datetime(
        2026, 10, 20, 9, 30, tzinfo=UTC
    )
    assert crosscheck.crosscheck_boi(db, date(2026, 10, 26)).reference_time == datetime(
        2026, 10, 26, 10, 30, tzinfo=UTC
    )


# --- G: incomplete candles dropped at ingestion -------------------------------------------
def test_recorded_coinbase_current_hour_dropped(db):
    body = (FIX / "coinbase_candles_1h.recorded-2026-10-31.partial.json").read_text()
    fetched = datetime(2026, 10, 31, 10, 57, 30, tzinfo=UTC)
    adapter = CoinbaseExchangeProvider(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=body)),
        sleep=lambda s: None,
        clock=lambda: fetched,
    )
    r = service.ingest_candles(
        db, "BTCUSD", adapter, "1h", fetched - timedelta(hours=4), fetched, detect_gaps=False
    )
    assert r.stored == 2 and r.dropped_incomplete == 1
    hours = db.scalars(select(MarketCandle.open_time).order_by(MarketCandle.open_time)).all()
    assert [h.hour for h in hours] == [8, 9]


# --- H: Saturday Twelve Data bars ----------------------------------------------------------
def test_utc_saturday_bars_stored_out_of_session_latest_dropped(db):
    adapter = TwelveDataProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: TD_RECEIVED,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=utc_shifted_series())),
    )
    r = service.ingest_candles(
        db,
        "USDILS",
        adapter,
        "1h",
        TD_RECEIVED - timedelta(hours=12),
        TD_RECEIVED,
        detect_gaps=False,
    )
    assert r.dropped_incomplete == 1 and r.statuses == {"suspect": 4}
    issues = db.scalars(select(MarketCandle.quality_issues)).all()
    assert all(i[0]["type"] == "out_of_session" for i in issues)


def test_recorded_non_utc_series_never_stored(db):
    body = (FIX / "twelvedata_time_series_1h_no_tz.recorded-2026-10-31.json").read_text()
    adapter = TwelveDataProvider(
        api_key="k",
        sleep=lambda s: None,
        clock=lambda: TD_RECEIVED,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=body)),
    )
    r = service.ingest_candles(
        db,
        "USDILS",
        adapter,
        "1h",
        TD_RECEIVED - timedelta(hours=12),
        TD_RECEIVED,
        detect_gaps=False,
    )
    assert not r.ok and "future" in r.error
    assert db.execute(text("SELECT count(*) FROM market_candles")).scalar() == 0


# --- Holiday calendars ---------------------------------------------------------------------
def test_seeded_holidays_are_labelled_assumptions(db):
    rows = db.scalars(select(MarketHoliday)).all()
    assert rows and all(r.is_assumption for r in rows)
    assert {r.calendar for r in rows} == {"fx", "xau", "boi"}


def test_fx_closed_on_christmas_session_day(db):
    t = service.resolve(db, "USDILS", "twelvedata")
    # Thu 24 Dec 2026 17:00 EST (22:00 UTC) -> Fri 25 Dec 17:00 EST: closed (assumption)
    assert t.calendar.is_open(datetime(2026, 12, 24, 21, 59, tzinfo=UTC))
    assert not t.calendar.is_open(datetime(2026, 12, 25, 12, 0, tzinfo=UTC))
    assert t.calendar.is_open(datetime(2026, 12, 23, 12, 0, tzinfo=UTC))
    btc = service.resolve(db, "BTCUSD", "coinbase")
    assert btc.calendar.is_open(datetime(2026, 12, 25, 12, 0, tzinfo=UTC))  # crypto 24/7


def test_no_missing_candle_events_during_holiday(db):
    t = service.resolve(db, "USDILS", "twelvedata")
    start = datetime(2026, 12, 25, 0, 0, tzinfo=UTC)
    assert service.record_gaps(db, t, "1h", start, start + timedelta(hours=12)) == 0


def test_israeli_rest_day_computation():
    assert yom_haatzmaut(2026) == date(2026, 4, 22)  # 5 Iyar on Wednesday
    assert yom_haatzmaut(2028) == date(2028, 5, 2)  # 5 Iyar on Monday -> Tuesday
    names = dict((d, n) for d, n in israeli_rest_days(2026))
    assert names[date(2026, 9, 21)] == "Yom Kippur"
    assert date(2026, 10, 27) not in names  # the missing 27 Oct is not a holiday
