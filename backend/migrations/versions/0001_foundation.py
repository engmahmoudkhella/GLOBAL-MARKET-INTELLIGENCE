"""Foundation: TimescaleDB, users, sessions, instruments, providers, audit, job runs.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False)


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "users",
        _id(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(20), server_default="viewer", nullable=False),
        sa.Column("preferred_language", sa.String(2), server_default="ar", nullable=False),
        sa.Column("timezone", sa.String(64), server_default="Asia/Gaza", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", TS, nullable=True),
        *_timestamps(),
        sa.CheckConstraint("role IN ('admin','analyst','viewer')", name="role"),
        sa.CheckConstraint("preferred_language IN ('ar','en')", name="preferred_language"),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "user_sessions",
        _id(),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_sessions_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "instruments",
        _id(),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("asset_class", sa.String(10), nullable=False),
        sa.Column("base_currency", sa.String(10), nullable=False),
        sa.Column("quote_currency", sa.String(10), nullable=False),
        sa.Column("role", sa.String(10), server_default="primary", nullable=False),
        sa.Column("market_status", sa.String(10), server_default="unknown", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("configuration_json", JSONB, nullable=False),
        *_timestamps(),
        sa.CheckConstraint("asset_class IN ('forex','metal','crypto')", name="asset_class"),
        sa.CheckConstraint("role IN ('primary','secondary')", name="role"),
        sa.CheckConstraint(
            "market_status IN ('unknown','open','closed','halted')", name="market_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("symbol", name="uq_instruments_symbol"),
    )

    op.create_table(
        "market_providers",
        _id(),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="not_configured", nullable=False),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("licence_notes", sa.Text(), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column(
            "configuration_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("last_success_at", TS, nullable=True),
        sa.Column("last_error_at", TS, nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "provider_type IN ('official','market_data','exchange','reference','economic','news')",
            name="provider_type",
        ),
        sa.CheckConstraint(
            "status IN ('not_configured','active','degraded','down','disabled')", name="status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_market_providers"),
        sa.UniqueConstraint("provider_name", name="uq_market_providers_provider_name"),
    )

    op.create_table(
        "instrument_provider_symbols",
        _id(),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_symbol", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(10), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("purpose IN ('primary','reference','secondary')", name="purpose"),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
            name="fk_instrument_provider_symbols_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["market_providers.id"],
            ondelete="RESTRICT",
            name="fk_instrument_provider_symbols_provider_id_market_providers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instrument_provider_symbols"),
        sa.UniqueConstraint("instrument_id", "provider_id", name="uq_instrument_provider"),
    )
    op.create_index(
        "ix_instrument_provider_symbols_instrument_id",
        "instrument_provider_symbols",
        ["instrument_id"],
    )
    op.create_index(
        "ix_instrument_provider_symbols_provider_id", "instrument_provider_symbols", ["provider_id"]
    )

    op.create_table(
        "system_audit_logs",
        _id(),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("details_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_system_audit_logs_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_system_audit_logs"),
    )
    op.create_index("ix_system_audit_logs_user_id", "system_audit_logs", ["user_id"])
    op.create_index("ix_system_audit_logs_action", "system_audit_logs", ["action"])
    op.create_index("ix_system_audit_logs_created_at", "system_audit_logs", ["created_at"])

    # Audit log is insert-only. The FK's ON DELETE SET NULL is the single permitted
    # update (it only nulls user_id), so the trigger allows exactly that change.
    op.execute("""
        CREATE FUNCTION gmi_audit_log_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE'
             AND NEW.user_id IS NULL AND OLD.user_id IS NOT NULL
             AND NEW.action = OLD.action
             AND NEW.entity_type IS NOT DISTINCT FROM OLD.entity_type
             AND NEW.entity_id IS NOT DISTINCT FROM OLD.entity_id
             AND NEW.details_json = OLD.details_json
             AND NEW.ip IS NOT DISTINCT FROM OLD.ip
             AND NEW.created_at = OLD.created_at THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'system_audit_logs is append-only (% rejected)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_append_only
        BEFORE UPDATE OR DELETE ON system_audit_logs
        FOR EACH ROW EXECUTE FUNCTION gmi_audit_log_guard();
    """)

    op.create_table(
        "job_runs",
        _id(),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("started_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("status IN ('running','succeeded','failed','skipped')", name="status"),
        sa.PrimaryKeyConstraint("id", name="pk_job_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_job_runs_idempotency_key"),
    )
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON system_audit_logs")
    op.execute("DROP FUNCTION IF EXISTS gmi_audit_log_guard()")
    op.drop_table("system_audit_logs")
    op.drop_table("instrument_provider_symbols")
    op.drop_table("market_providers")
    op.drop_table("instruments")
    op.drop_table("user_sessions")
    op.drop_table("users")
    # The timescaledb extension is intentionally left installed.
