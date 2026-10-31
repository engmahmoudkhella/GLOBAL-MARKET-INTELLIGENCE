"""Celery application. Task bodies are thin wrappers; logic lives in modules."""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.signals import beat_init

from app.core.config import Settings, get_settings

_settings = get_settings()

celery_app = Celery(
    "gmi",
    broker=_settings.redis_url,
    backend=None,
    include=["app.tasks.system", "app.tasks.ingestion"],
)


def build_schedule(settings: Settings) -> dict[str, dict[str, Any]]:
    schedule: dict[str, dict[str, Any]] = {
        "system-heartbeat": {"task": "gmi.system.heartbeat", "schedule": 60.0},
    }
    if settings.ingestion_enabled:
        from app.tasks.ingestion import ingestion_schedule

        schedule.update(ingestion_schedule(settings))
    return schedule


def verify_twelvedata_plan(settings: Settings) -> str | None:
    """Startup check (beat): actual plan limits from /api_usage must cover the schedule.
    Raises RuntimeError (beat refuses to start) when they do not."""
    if not (settings.ingestion_enabled and settings.twelvedata_api_key is not None):
        return None
    from app.ingestion.budget import check_against_plan
    from app.providers.twelvedata import TwelveDataProvider

    adapter = TwelveDataProvider()
    try:
        plan = adapter.get_plan()
    finally:
        adapter.close()
    result = check_against_plan(
        settings.twelvedata_schedule(),
        settings.twelvedata_credits_per_minute,
        settings.twelvedata_credits_per_day,
        settings.twelvedata_budget_headroom,
        plan.per_minute,
        plan.per_day,
        plan.category,
    )
    if not result.ok:
        raise RuntimeError(result.message)
    return result.message


@beat_init.connect  # type: ignore[untyped-decorator]
def _on_beat_init(**_: Any) -> None:
    msg = verify_twelvedata_plan(get_settings())
    if msg:
        logging.getLogger(__name__).info(msg)


celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_time_limit=300,
    beat_schedule=build_schedule(_settings),
)
