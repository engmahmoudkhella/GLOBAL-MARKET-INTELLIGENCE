from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    session: Session,
    action: str,
    *,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Append an audit entry to the current transaction (caller commits)."""
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            details_json=details or {},
            ip=ip,
        )
    )
