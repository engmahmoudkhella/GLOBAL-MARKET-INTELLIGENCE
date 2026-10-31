from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def check_database() -> dict[str, Any]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            ts = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            ).scalar()
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return {"ok": True, "timescaledb": ts, "migration": rev}
    except Exception as exc:  # noqa: BLE001
        log.warning("database health check failed: %s", type(exc).__name__)
        return {"ok": False, "error": type(exc).__name__}


def check_redis() -> dict[str, Any]:
    try:
        import redis

        r = redis.Redis.from_url(
            get_settings().redis_url, socket_timeout=1, socket_connect_timeout=1
        )
        r.ping()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def readiness() -> dict[str, Any]:
    checks = {"database": check_database(), "redis": check_redis()}
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    result = readiness()
    # Public readiness exposes only booleans; details are on the admin endpoint.
    body = {"ok": result["ok"], "checks": {k: v["ok"] for k, v in result["checks"].items()}}
    return JSONResponse(body, status_code=200 if result["ok"] else 503)
