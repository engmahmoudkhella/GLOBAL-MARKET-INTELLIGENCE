from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
TEST_PASSWORD = "correct horse battery staple"


def _clear_caches() -> None:
    from app.core import db, rate_limit
    from app.core.config import get_settings

    get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()
    rate_limit.get_backend.cache_clear()


def alembic_config(url: str) -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_DATABASE_URL not set; integration tests skipped")
    name = f"gmi_test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    os.environ["GMI_DATABASE_URL"] = url
    _clear_caches()
    command.upgrade(alembic_config(url), "head")
    try:
        yield url
    finally:
        from app.core.db import get_engine

        get_engine().dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def db(database_url: str) -> Iterator[Session]:
    from app.core.db import get_engine, get_sessionmaker

    with get_engine().begin() as c:
        # TRUNCATE does not fire the row-level append-only trigger.
        c.execute(
            text(
                "TRUNCATE users, user_sessions, system_audit_logs, job_runs, "
                "market_quotes, market_candles, data_quality_events, "
                "official_reference_rates RESTART IDENTITY CASCADE"
            )
        )
        c.execute(
            text(
                "UPDATE market_providers SET status='not_configured', consecutive_failures=0, "
                "capabilities='[]'::jsonb, last_success_at=NULL, last_error_at=NULL"
            )
        )
    from app.core.rate_limit import get_backend

    backend = get_backend()
    if hasattr(backend, "reset"):
        backend.reset()
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def make_user(db: Session, email: str = "owner@example.com", role: str = "admin") -> int:
    from app.auth import service

    u = service.create_user(db, email=email, name="Owner", password=TEST_PASSWORD, role=role)
    db.commit()
    return u.id


def login(client: TestClient, email: str = "owner@example.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return client.cookies["gmi_csrf"]
