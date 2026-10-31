from decimal import Decimal

from pydantic import SecretStr

from app.core.config import Settings
from app.ingestion.budget import check_budget
from app.providers.registry import FACTORIES
from app.tasks.celery_app import build_schedule


def settings(**kw):
    return Settings.model_construct(**{**Settings().model_dump(), **kw})


def test_ingestion_not_scheduled_unless_enabled():
    assert set(build_schedule(settings(ingestion_enabled=False))) == {"system-heartbeat"}


def test_without_key_no_twelvedata_tasks():
    sched = build_schedule(settings(ingestion_enabled=True, twelvedata_api_key=None))
    providers = {e["args"][1] for e in sched.values() if "args" in e}
    assert "twelvedata" not in providers and providers <= set(FACTORIES)
    assert "usdils-boi-crosscheck" not in sched


def test_with_key_schedule_matches_budget_model():
    s = settings(
        ingestion_enabled=True,
        twelvedata_api_key=SecretStr("k"),
        twelvedata_quote_interval_seconds=30,
        twelvedata_candles_1m_interval_seconds=120,
    )
    sched = build_schedule(s)
    td = {
        k: e
        for k, e in sched.items()
        if e.get("args", ("", ""))[1] == "twelvedata" and e["task"].startswith("gmi.ingest")
    }
    # 2 symbols x (quote, 1m candles, 1h candles) = the budget model's call set
    assert len(td) == 6
    intervals = sorted({int(e["schedule"]) for e in td.values()})
    assert intervals == sorted(set(s.twelvedata_schedule().intervals()))
    assert check_budget(s.twelvedata_schedule(), 55, 0, Decimal("0.9")).ok
    assert "usdils-boi-crosscheck" in sched


def test_no_provider_daily_or_4h_ingestion_and_btc_only_from_coinbase():
    sched = build_schedule(settings(ingestion_enabled=True, twelvedata_api_key=SecretStr("k")))
    ingest = [e for e in sched.values() if e["task"] == "gmi.ingest.candles"]
    assert {e["args"][2] for e in ingest} <= {"1m", "5m", "15m", "1h"}
    derived = {
        (e["args"][0], e["args"][2]) for e in sched.values() if e["task"] == "gmi.derive.candles"
    }
    assert derived == {
        (s, tf) for s in ("BTCUSD", "USDILS", "XAUUSD", "BTCUSDT") for tf in ("4h", "1d")
    }
    assert {
        e["args"][1]
        for e in sched.values()
        if e.get("args", ("",))[0] == "BTCUSD" and e["task"].startswith("gmi.ingest")
    } == {"coinbase"}


def test_binance_only_feeds_btcusdt_and_can_be_disabled():
    sched = build_schedule(settings(ingestion_enabled=True))
    binance = {e["args"][0] for e in sched.values() if e.get("args", ("", ""))[1] == "binance"}
    assert binance == {"BTCUSDT"}
    off = build_schedule(settings(ingestion_enabled=True, binance_enabled=False))
    assert not any(e.get("args", ("", ""))[1] == "binance" for e in off.values())


def test_coingecko_reference_scheduled_only_with_key():
    assert "btcusd-coingecko-reference" not in build_schedule(settings(ingestion_enabled=True))
    sched = build_schedule(settings(ingestion_enabled=True, coingecko_demo_api_key=SecretStr("cg")))
    entry = sched["btcusd-coingecko-reference"]
    assert entry["task"] == "gmi.ingest.reference_quote"
    assert entry["args"] == ("BTCUSD", "coingecko", 300)


def test_coingecko_budget():
    from app.ingestion.budget import check_coingecko_budget

    # 300 s: 1/min, ceil(31*86400/300) = 8928/month <= 9000
    assert check_coingecko_budget(300, 30, 10_000, Decimal("0.9")) is None
    msg = check_coingecko_budget(60, 30, 10_000, Decimal("0.9"))  # 44640/month
    assert msg and "44640 calls/month" in msg
