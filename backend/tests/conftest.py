"""Shared test configuration.

Unit tests need nothing external. Integration tests (marked `integration`) need a
PostgreSQL+TimescaleDB server: set TEST_DATABASE_URL to a superuser URL, e.g.
  postgresql+psycopg://gmi:gmi@localhost:55432/gmi
A throwaway database is created per test session and dropped afterwards.
"""

from __future__ import annotations

import os

# Must be set before any app module reads settings.
os.environ.setdefault("GMI_ENVIRONMENT", "test")
os.environ["GMI_RATE_LIMIT_BACKEND"] = "memory"
os.environ["GMI_COOKIE_SECURE"] = "false"
os.environ.setdefault("GMI_REDIS_URL", "redis://localhost:6399/0")
os.environ.setdefault("GMI_LOG_LEVEL", "WARNING")
