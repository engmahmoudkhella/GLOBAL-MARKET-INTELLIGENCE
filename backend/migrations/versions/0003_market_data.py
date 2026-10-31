"""Market data: quotes and candles (hypertables), data-quality events, reference rates.

Retention (decision D7): candles are compressed after 2 years and never dropped automatically;
quotes are compressed after 7 days and dropped after 90 days.

Revision ID: 0003_market_data
Revises: 0002_seed_reference_data
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_market_data"
down_revision = "0002_seed_reference_data"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)
PRICE = sa.Numeric(24, 10)
QUALITY = "data_quality_status IN ('verified','suspect','rejected')"


def _fk(table: str, col: str, ref: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [col], [f"{ref}.id"], ondelete="RESTRICT", name=f"fk_{table}_{col}_{ref}"
    )


def upgrade() -> None:
    op.create_table(
        "market_quotes",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", TS, nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.Column("bid", PRICE),
        sa.Column("ask", PRICE),
        sa.Column("mid", PRICE),
        sa.Column("last_price", PRICE),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("data_quality_status", sa.String(10), nullable=False),
        sa.Column("quality_issues", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.CheckConstraint(QUALITY, name="data_quality_status"),
        _fk("market_quotes", "instrument_id", "instruments"),
        _fk("market_quotes", "provider_id", "market_providers"),
        sa.PrimaryKeyConstraint(
            "instrument_id", "provider_id", "observed_at", name="pk_market_quotes"
        ),
    )
    op.create_table(
        "market_candles",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(3), nullable=False),
        sa.Column("open_time", TS, nullable=False),
        sa.Column("close_time", TS, nullable=False),
        sa.Column("open", PRICE, nullable=False),
        sa.Column("high", PRICE, nullable=False),
        sa.Column("low", PRICE, nullable=False),
        sa.Column("close", PRICE, nullable=False),
        sa.Column("volume", sa.Numeric(38, 10)),
        sa.Column("is_complete", sa.Boolean(), nullable=False),
        sa.Column("received_at", TS, nullable=False),
        sa.Column("data_quality_status", sa.String(10), nullable=False),
        sa.Column("quality_issues", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.CheckConstraint(QUALITY, name="data_quality_status"),
        sa.CheckConstraint("timeframe IN ('1m','5m','15m','1h','4h','1d')", name="timeframe"),
        _fk("market_candles", "instrument_id", "instruments"),
        _fk("market_candles", "provider_id", "market_providers"),
        sa.PrimaryKeyConstraint(
            "instrument_id", "provider_id", "timeframe", "open_time", name="pk_market_candles"
        ),
    )
    # Hypertables. Default indexes are disabled: the composite primary keys already lead
    # with the series identity and end with the time column.
    op.execute(
        "SELECT create_hypertable('market_quotes', by_range('observed_at', "
        "INTERVAL '1 day'), create_default_indexes => false)"
    )
    op.execute(
        "SELECT create_hypertable('market_candles', by_range('open_time', "
        "INTERVAL '7 days'), create_default_indexes => false)"
    )
    op.execute("""ALTER TABLE market_quotes SET (timescaledb.compress,
        timescaledb.compress_segmentby = 'instrument_id, provider_id',
        timescaledb.compress_orderby = 'observed_at DESC')""")
    op.execute("""ALTER TABLE market_candles SET (timescaledb.compress,
        timescaledb.compress_segmentby = 'instrument_id, provider_id, timeframe',
        timescaledb.compress_orderby = 'open_time DESC')""")
    op.execute("SELECT add_compression_policy('market_quotes', INTERVAL '7 days')")
    op.execute("SELECT add_retention_policy('market_quotes', INTERVAL '90 days')")
    op.execute("SELECT add_compression_policy('market_candles', INTERVAL '2 years')")

    op.create_table(
        "data_quality_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("instrument_id", sa.BigInteger()),
        sa.Column("provider_id", sa.BigInteger()),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("detected_at", TS, nullable=False),
        sa.Column("window_start", TS),
        sa.Column("window_end", TS),
        sa.Column("details_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("severity IN ('reject','suspect','info')", name="severity"),
        _fk("data_quality_events", "instrument_id", "instruments"),
        _fk("data_quality_events", "provider_id", "market_providers"),
        sa.PrimaryKeyConstraint("id", name="pk_data_quality_events"),
    )
    op.create_index(
        "ix_dq_events_instrument_detected", "data_quality_events", ["instrument_id", "detected_at"]
    )
    op.create_index("ix_data_quality_events_provider_id", "data_quality_events", ["provider_id"])

    op.create_table(
        "official_reference_rates",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", PRICE, nullable=False),
        sa.Column("published_at", TS),
        sa.Column("received_at", TS, nullable=False),
        _fk("official_reference_rates", "instrument_id", "instruments"),
        _fk("official_reference_rates", "provider_id", "market_providers"),
        sa.PrimaryKeyConstraint("id", name="pk_official_reference_rates"),
        sa.UniqueConstraint("instrument_id", "provider_id", "rate_date", name="uq_reference_rate"),
    )
    op.create_index(
        "ix_official_reference_rates_provider_id", "official_reference_rates", ["provider_id"]
    )

    # BoI provider symbol: the SDMX series is derived from the currency key (RER_USD_ILS).
    op.execute("""UPDATE instrument_provider_symbols SET notes =
        'BoI representative rate (SDMX series RER_USD_ILS; latest via PublicApi). Reference only, not executable.'
        WHERE provider_symbol = 'USD'
          AND provider_id = (SELECT id FROM market_providers WHERE provider_name = 'boi')""")


def downgrade() -> None:
    op.drop_table("official_reference_rates")
    op.drop_table("data_quality_events")
    op.drop_table("market_candles")
    op.drop_table("market_quotes")
    op.execute("""UPDATE instrument_provider_symbols SET notes =
        'BoI representative rate; series identifier to be confirmed in Phase 2. Not executable.'
        WHERE provider_symbol = 'USD'
          AND provider_id = (SELECT id FROM market_providers WHERE provider_name = 'boi')""")
