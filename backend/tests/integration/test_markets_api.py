from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import pytest

from app.core.clock import utcnow
from app.ingestion import service
from app.providers.models import ReferenceRate
from tests.integration.conftest import login, make_user
from tests.integration.test_ingestion import FakeBoi, FakeCoinbase, c, q

pytestmark = pytest.mark.integration


@pytest.fixture
def authed(client, db):
    make_user(db, role="viewer")
    login(client)
    return client


def test_markets_require_auth(client):
    assert client.get("/api/v1/markets/BTCUSD/quote").status_code == 401


def test_quote_without_data_is_explicitly_empty(authed):
    body = authed.get("/api/v1/markets/USDILS/quote").json()
    assert body["data_status"] == "no_data" and body["signals_allowed"] is False
    assert body["provider"] == "twelvedata"
    assert body["bid"] is None and body["mid"] is None and body["observed_at"] is None


def test_quote_returns_source_timestamps_and_string_prices(authed, db):
    fake = FakeCoinbase()
    now = utcnow().replace(microsecond=0)
    fake.quotes = [q(now - timedelta(seconds=5), bid="70000.10", ask="70000.30")]
    service.ingest_quote(db, "BTCUSD", fake)
    body = authed.get("/api/v1/markets/btcusd/quote").json()
    assert body["provider"] == "coinbase" and body["data_status"] == "fresh"
    assert body["signals_allowed"] is True
    assert body["bid"] == "70000.1000000000" and body["mid"] == "70000.2000000000"
    assert body["price_type"] == "mid"
    assert body["observed_at"].startswith((now - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M"))
    assert body["data_quality_status"] == "verified"


def test_stale_quote_disables_signals(authed, db):
    fake = FakeCoinbase()
    fake.quotes = [q(utcnow() - timedelta(minutes=10))]
    service.ingest_quote(db, "BTCUSD", fake)
    body = authed.get("/api/v1/markets/BTCUSD/quote").json()
    assert body["data_status"] == "stale" and body["signals_allowed"] is False
    assert body["mid"] is not None  # shown, but flagged


def test_candles_endpoint_filters_rejected_and_validates_range(authed, db):
    t0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    fake = FakeCoinbase()
    fake.candles = [c(t0), c(t0 + timedelta(minutes=1), h="1")]  # second is invalid
    service.ingest_candles(
        db, "BTCUSD", fake, "1m", t0, t0 + timedelta(minutes=2), detect_gaps=False
    )
    params = {
        "timeframe": "1m",
        "start": t0.isoformat(),
        "end": (t0 + timedelta(minutes=5)).isoformat(),
    }
    body = authed.get("/api/v1/markets/BTCUSD/candles", params=params).json()
    assert body["provider"] == "coinbase" and body["count"] == 1
    assert body["items"][0]["close"] == "100.5000000000"
    all_rows = authed.get(
        "/api/v1/markets/BTCUSD/candles", params={**params, "include_rejected": True}
    ).json()
    assert all_rows["count"] == 2
    bad = authed.get(
        "/api/v1/markets/BTCUSD/candles",
        params={**params, "start": params["end"], "end": params["start"]},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "bad_range"
    assert (
        authed.get("/api/v1/markets/BTCUSD/candles", params={"timeframe": "3m"}).status_code == 422
    )
    assert (
        authed.get("/api/v1/markets/BTCUSD/candles", params={"provider": "binance"}).status_code
        == 404
    )  # not mapped


def test_reference_rates_endpoint(authed, db):
    today = utcnow().date()
    boi = FakeBoi([ReferenceRate("USD", today - timedelta(days=1), D("3.71"), utcnow())])
    service.ingest_reference_rates(db, "USDILS", boi, today - timedelta(days=5), today)
    body = authed.get("/api/v1/markets/USDILS/reference-rates").json()
    assert body["provider"] == "boi" and "Not an executable price" in body["note"]
    assert body["items"] == [
        {
            "rate_date": (today - timedelta(days=1)).isoformat(),
            "rate": "3.7100000000",
            "published_at": None,
            "received_at": body["items"][0]["received_at"],
        }
    ]
    assert date.fromisoformat(body["items"][0]["rate_date"]) < today


def test_unknown_symbol_404(authed):
    assert authed.get("/api/v1/markets/EURUSD/quote").status_code == 404
