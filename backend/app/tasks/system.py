from __future__ import annotations

from typing import Any

from app.core.clock import utcnow
from app.core.db import get_sessionmaker
from app.jobs.runner import run_idempotent
from app.tasks.celery_app import celery_app


def heartbeat_key(now: Any = None) -> str:
    now = now or utcnow()
    return f"heartbeat:{now.strftime('%Y-%m-%dT%H:%M')}"


@celery_app.task(name="gmi.system.heartbeat")  # type: ignore[untyped-decorator]
def heartbeat() -> str:
    """Proves worker + beat + DB are alive; visible at /api/v1/admin/jobs."""
    with get_sessionmaker()() as session:
        return run_idempotent(
            session, "system.heartbeat", heartbeat_key(), lambda: {"worker": "ok"}
        )
