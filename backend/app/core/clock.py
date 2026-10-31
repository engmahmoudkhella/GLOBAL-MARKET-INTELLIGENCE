"""Injectable UTC clock. All timestamps in the system are timezone-aware UTC."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
