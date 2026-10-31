"""Celery application. Task bodies are thin wrappers; logic lives in modules."""

from __future__ import annotations

from typing import Any

from celery import Celery

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
