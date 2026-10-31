import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.models import Base
from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.integration


def test_timescaledb_extension_installed(database_url):
    eng = create_engine(database_url)
    with eng.connect() as c:
        assert (
            c.execute(text("SELECT 1 FROM pg_extension WHERE extname='timescaledb'")).scalar() == 1
        )
    eng.dispose()


def test_models_match_migrations(database_url):
    """ORM metadata and migrations must not drift (every change goes through a migration)."""
    eng = create_engine(database_url)
    with eng.connect() as c:
        diff = compare_metadata(
            MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata
        )
    eng.dispose()
    assert diff == []


def test_downgrade_and_upgrade_roundtrip(database_url):
    cfg = alembic_config(database_url)
    from app.core.db import get_engine

    get_engine().dispose()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = create_engine(database_url)
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM instruments")).scalar() == 4
    eng.dispose()
