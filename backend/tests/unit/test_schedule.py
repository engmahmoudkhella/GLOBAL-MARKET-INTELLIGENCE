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
    assert derived == {(s, tf) for s in ("BTCUSD", "USDILS", "XAUUSD") for tf in ("4h", "1d")}
    assert {
        e["args"][1]
        for e in sched.values()
        if e.get("args", ("",))[0] == "BTCUSD" and e["task"].startswith("gmi.ingest")
    } == {"coinbase"}
