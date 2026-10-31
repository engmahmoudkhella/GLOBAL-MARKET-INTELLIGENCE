"""Celery ingestion tasks. Scheduled only when GMI_INGESTION_ENABLED=true.

Each run is recorded in job_runs with a time-bucketed idempotency key, so a duplicate beat
tick in the same bucket is skipped. Provider calls are skipped while the instrument's session
calendar has been closed for the whole lookback window (saves Twelve Data credits).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.ingestion import aggregate, crosscheck, service
from app.ingestion.budget import CANDLES_1H_INTERVAL_SECONDS
from app.jobs.runner import run_idempotent
from app.providers import registry
from app.providers.models import Timeframe
from app.tasks.celery_app import celery_app


class RetryLater(RuntimeError):
    """Raised so job_runs records 'failed' and the next tick retries."""


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


def _session_closed(
    session: Any, symbol: str, provider: str, now: datetime, lookback: timedelta
) -> bool:
    cal = service.resolve(session, symbol, provider).calendar
    return not cal.is_open_during(now - lookback, lookback + timedelta(minutes=1))


@celery_app.task(name="gmi.ingest.quote")  # type: ignore[untyped-decorator]
def ingest_quote(symbol: str, provider: str, interval_seconds: int = 60) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        if _session_closed(session, symbol, provider, now, timedelta(seconds=interval_seconds)):
            return {"skipped": "session closed"}
        adapter = registry.create(provider)
        try:
            return _result(service.ingest_quote(session, symbol, adapter))
        finally:
            adapter.close()

    return _run(f"ingest.quote.{symbol}.{provider}", min(interval_seconds, 60), body)


@celery_app.task(name="gmi.ingest.candles")  # type: ignore[untyped-decorator]
def ingest_candles(symbol: str, provider: str, timeframe: Timeframe, lookback_minutes: int) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        lookback = timedelta(minutes=lookback_minutes)
        if _session_closed(session, symbol, provider, now, lookback):
            return {"skipped": "session closed"}
        adapter = registry.create(provider)
        try:
            return _result(
                service.ingest_candles(session, symbol, adapter, timeframe, now - lookback, now)
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


@celery_app.task(name="gmi.derive.candles")  # type: ignore[untyped-decorator]
def derive_candles(symbol: str, provider: str, timeframe: str, lookback_hours: int) -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        r = aggregate.build_derived(
            session,
            symbol,
            provider,
            timeframe,  # type: ignore[arg-type]
            now - timedelta(hours=lookback_hours),
            now,
            now,
        )
        return _result(r)

    return _run(f"derive.candles.{symbol}.{provider}.{timeframe}", 600, body)


@celery_app.task(name="gmi.quality.boi_crosscheck")  # type: ignore[untyped-decorator]
def boi_crosscheck(days: int = 3) -> str:
    """One idempotent job per BoI rate date; retried while the market price is still missing."""
    results: list[str] = []
    with get_sessionmaker()() as session:
        today = utcnow().date()
        for d in (today - timedelta(days=i) for i in range(days)):

            def body(day: Any = d) -> dict[str, Any]:
                r = crosscheck.crosscheck_boi(session, day)
                if r.status == "no_market_price" and day >= today - timedelta(days=1):
                    raise RetryLater(f"no Twelve Data price near BoI publication on {day}")
                return {
                    "status": r.status,
                    "diff_pct": r.diff_pct,
                    "price": r.market_price,
                    "reference": r.reference_rate,
                }

            try:
                results.append(
                    run_idempotent(
                        session,
                        "quality.boi_crosscheck",
                        f"quality.boi_crosscheck:USDILS:{d}",
                        body,
                    )
                )
            except RetryLater:
                results.append("retry")
    return ",".join(results)


@celery_app.task(name="gmi.quality.freshness")  # type: ignore[untyped-decorator]
def check_freshness() -> str:
    def body(session: Any, now: datetime) -> dict[str, Any]:
        return {
            s: service.record_staleness(session, s, now).status
            for s in ("USDILS", "XAUUSD", "BTCUSD")
        }

    return _run("quality.freshness", 60, body)


def ingestion_schedule(s: Settings) -> dict[str, dict[str, Any]]:
    sched: dict[str, dict[str, Any]] = {
        "btcusd-quote": {
            "task": "gmi.ingest.quote",
            "schedule": 15.0,
            "args": ("BTCUSD", "coinbase", 15),
        },
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
        "usdils-boi-reference": {
            "task": "gmi.ingest.reference",
            "schedule": 1800.0,
            "args": ("USDILS", "boi", 10),
        },
        "freshness": {"task": "gmi.quality.freshness", "schedule": 60.0},
    }
    derive_targets = [("BTCUSD", "coinbase")]
    if s.twelvedata_api_key is not None:
        q, c1m = s.twelvedata_quote_interval_seconds, s.twelvedata_candles_1m_interval_seconds
        for sym, psym in (("USDILS", "usdils"), ("XAUUSD", "xauusd")):
            sched[f"{psym}-quote"] = {
                "task": "gmi.ingest.quote",
                "schedule": float(q),
                "args": (sym, "twelvedata", q),
            }
            sched[f"{psym}-candles-1m"] = {
                "task": "gmi.ingest.candles",
                "schedule": float(c1m),
                "args": (sym, "twelvedata", "1m", c1m // 60 + 10),
            }
            sched[f"{psym}-candles-1h"] = {
                "task": "gmi.ingest.candles",
                "schedule": float(CANDLES_1H_INTERVAL_SECONDS),
                "args": (sym, "twelvedata", "1h", 12 * 60),
            }
            derive_targets.append((sym, "twelvedata"))
        sched["usdils-boi-crosscheck"] = {"task": "gmi.quality.boi_crosscheck", "schedule": 3600.0}
    for sym, prov in derive_targets:
        sched[f"{sym.lower()}-derive-4h"] = {
            "task": "gmi.derive.candles",
            "schedule": 900.0,
            "args": (sym, prov, "4h", 48),
        }
        sched[f"{sym.lower()}-derive-1d"] = {
            "task": "gmi.derive.candles",
            "schedule": 3600.0,
            "args": (sym, prov, "1d", 5 * 24),
        }
    return sched
