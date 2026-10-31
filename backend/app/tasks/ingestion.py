"""Celery ingestion tasks. Scheduled only when GMI_INGESTION_ENABLED=true.

Each run is recorded in job_runs with a time-bucketed idempotency key, so a duplicate beat
tick in the same bucket is skipped.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.clock import utcnow
from app.core.db import get_sessionmaker
from app.ingestion import service
from app.jobs.runner import run_idempotent
from app.providers import registry
from app.providers.models import Timeframe
from app.tasks.celery_app import celery_app


def _bucket(now: datetime, seconds: int) -> str:
    return datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, now.tzinfo).strftime(
        "%Y%m%dT%H%M%S"
    )


def _run(job: str, bucket_seconds: int, fn: Any) -> str:
    now = utcnow()
    with get_sessionmaker()() as session:
        return run_idempotent(
            session, job, f"{job}:{_bucket(now, bucket_seconds)}", lambda: fn(session, now)
        )


def _result(r: service.IngestResult) -> dict[str, Any]:
    if not r.ok:
        # Provider failure is already recorded on market_providers; surface it in job_runs.
        raise RuntimeError(r.error or "provider failure")
    return {"stored": r.stored, "skipped": r.skipped, "statuses": r.statuses, "issues": r.issues}


@celery_app.task(name="gmi.ingest.quote")  # type: ignore[untyped-decorator]
def ingest_quote(symbol: str, provider: str) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        adapter = registry.create(provider)
        try:
            return _result(service.ingest_quote(session, symbol, adapter))
        finally:
            adapter.close()

    return _run(f"ingest.quote.{symbol}.{provider}", 10, body)


@celery_app.task(name="gmi.ingest.candles")  # type: ignore[untyped-decorator]
def ingest_candles(symbol: str, provider: str, timeframe: Timeframe, lookback_minutes: int) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        adapter = registry.create(provider)
        try:
            return _result(
                service.ingest_candles(
                    session,
                    symbol,
                    adapter,
                    timeframe,
                    now - timedelta(minutes=lookback_minutes),
                    now,
                )
            )
        finally:
            adapter.close()

    return _run(f"ingest.candles.{symbol}.{provider}.{timeframe}", 60, body)


@celery_app.task(name="gmi.ingest.reference")  # type: ignore[untyped-decorator]
def ingest_reference(symbol: str, provider: str, lookback_days: int) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        adapter = registry.create(provider)
        try:
            today = now.date()
            return _result(
                service.ingest_reference_rates(
                    session, symbol, adapter, today - timedelta(days=lookback_days), today
                )
            )
        finally:
            adapter.close()

    return _run(f"ingest.reference.{symbol}.{provider}", 600, body)


@celery_app.task(name="gmi.quality.freshness")  # type: ignore[untyped-decorator]
def check_freshness() -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        return {
            s: service.record_staleness(session, s, now).status
            for s in ("USDILS", "XAUUSD", "BTCUSD")
        }

    return _run("quality.freshness", 60, body)


INGESTION_SCHEDULE: dict[str, dict[str, Any]] = {
    "btcusd-quote": {"task": "gmi.ingest.quote", "schedule": 15.0, "args": ("BTCUSD", "coinbase")},
    "btcusd-candles-1m": {
        "task": "gmi.ingest.candles",
        "schedule": 60.0,
        "args": ("BTCUSD", "coinbase", "1m", 30),
    },
    "btcusd-candles-1h": {
        "task": "gmi.ingest.candles",
        "schedule": 900.0,
        "args": ("BTCUSD", "coinbase", "1h", 12 * 60),
    },
    "btcusd-candles-1d": {
        "task": "gmi.ingest.candles",
        "schedule": 3600.0,
        "args": ("BTCUSD", "coinbase", "1d", 5 * 24 * 60),
    },
    "usdils-boi-reference": {
        "task": "gmi.ingest.reference",
        "schedule": 1800.0,
        "args": ("USDILS", "boi", 10),
    },
    "freshness": {"task": "gmi.quality.freshness", "schedule": 60.0},
}
