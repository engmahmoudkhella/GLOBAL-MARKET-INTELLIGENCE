"""Celery application. Task bodies are thin wrappers; logic lives in modules."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery("gmi", broker=_settings.redis_url, backend=None, include=["app.tasks.system"])
celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "system-heartbeat": {"task": "gmi.system.heartbeat", "schedule": 60.0},
    },
)
