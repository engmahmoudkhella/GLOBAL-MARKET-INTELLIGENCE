from app.tasks.celery_app import build_schedule


def test_ingestion_not_scheduled_unless_enabled():
    assert set(build_schedule(False)) == {"system-heartbeat"}


def test_ingestion_schedule_uses_only_registered_providers():
    from app.providers.registry import FACTORIES

    sched = build_schedule(True)
    providers = {e["args"][1] for e in sched.values() if "args" in e}
    assert providers <= set(FACTORIES)
    assert "twelvedata" not in providers  # on hold until coverage is confirmed
    # BTCUSD is only ever ingested from USD-quoted Coinbase
    assert {e["args"][1] for e in sched.values() if e.get("args", ("",))[0] == "BTCUSD"} == {
        "coinbase"
    }
