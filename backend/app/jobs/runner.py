"""Idempotent job execution recorded in job_runs (SRS §19: job idempotency)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.clock import utcnow

Outcome = Literal["succeeded", "failed", "skipped"]


def run_idempotent(
    session: Session,
    job_name: str,
    idempotency_key: str,
    fn: Callable[[], dict[str, Any] | None],
) -> Outcome:
    """Run `fn` at most once successfully per idempotency key.

    A key that already succeeded (or is running) is skipped. A key that failed may be retried.
    """
    claimed = session.execute(
        text("""
            INSERT INTO job_runs (job_name, idempotency_key, status)
            VALUES (:job, :key, 'running')
            ON CONFLICT (idempotency_key) DO UPDATE
              SET status = 'running', started_at = now(), finished_at = NULL, error = NULL
              WHERE job_runs.status = 'failed'
            RETURNING id
        """),
        {"job": job_name, "key": idempotency_key},
    ).scalar()
    session.commit()
    if claimed is None:
        return "skipped"
    try:
        details = fn() or {}
    except Exception as exc:
        session.rollback()
        session.execute(
            text("UPDATE job_runs SET status='failed', finished_at=:t, error=:e WHERE id=:id"),
            {"t": utcnow(), "e": f"{type(exc).__name__}: {exc}"[:2000], "id": claimed},
        )
        session.commit()
        raise
    import json

    session.execute(
        text("""UPDATE job_runs SET status='succeeded', finished_at=:t,
                details_json=CAST(:d AS jsonb) WHERE id=:id"""),
        {"t": utcnow(), "d": json.dumps(details, default=str), "id": claimed},
    )
    session.commit()
    return "succeeded"
