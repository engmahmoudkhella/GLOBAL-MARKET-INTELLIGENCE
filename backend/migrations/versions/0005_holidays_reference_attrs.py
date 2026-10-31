"""Holiday calendars, BoI publication calendar, raw reference-rate attributes.

* market_holidays: closures per calendar key ('fx', 'xau', 'boi'). Every seeded row is an
  ASSUMPTION (is_assumption=true) until confirmed by observed data; gap events reveal mismatches.
* official_reference_rates.attributes_json: provider attributes stored raw (e.g. SDMX
  RELEASE_STATUS, series attributes, PublicApi unit / currentChange %), not interpreted.
* instruments: sessions.holiday_calendar = 'fx' (USDILS) / 'xau' (XAUUSD).

BoI rows (weekdays only) generated 2026-10-31 with app.markets.holidays.israeli_rest_days
(pyluach + statutory Yom HaAtzmaut postponement) and pasted as literals.

Revision ID: 0005_holidays_reference_attrs
Revises: 0004_derived_candles
Create Date: 2026-10-31
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_holidays_reference_attrs"
down_revision = "0004_derived_candles"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)
NY = ZoneInfo("America/New_York")
IL = ZoneInfo("Asia/Jerusalem")

BOI_REST_DAYS = [
    ("2026-04-02", "1 Pesach"),
    ("2026-04-08", "7 Pesach"),
    ("2026-04-22", "Yom HaAtzmaut"),
    ("2026-05-22", "Shavuos"),
    ("2026-09-21", "Yom Kippur"),
    ("2027-04-22", "1 Pesach"),
    ("2027-04-28", "7 Pesach"),
    ("2027-05-12", "Yom HaAtzmaut"),
    ("2027-06-11", "Shavuos"),
    ("2027-10-11", "Yom Kippur"),
    ("2028-04-11", "1 Pesach"),
    ("2028-04-17", "7 Pesach"),
    ("2028-05-02", "Yom HaAtzmaut"),
    ("2028-05-31", "Shavuos"),
    ("2028-09-21", "1 Rosh Hashana"),
    ("2028-09-22", "2 Rosh Hashana"),
    ("2028-10-05", "1 Succos"),
    ("2028-10-12", "Shmini Atzeres"),
]

# FX and spot gold: the session day ending 17:00 New York on these dates is treated as closed.
# ASSUMPTION (common FX/spot-metals convention); verify against Twelve Data behaviour.
FX_XAU_DAYS = [
    ("2026-12-25", "Christmas Day"),
    ("2027-01-01", "New Year's Day"),
    ("2028-12-25", "Christmas Day"),
]  # weekday fixed dates only


def upgrade() -> None:
    op.create_table(
        "market_holidays",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("calendar", sa.String(20), nullable=False),
        sa.Column("closed_from", TS, nullable=False),
        sa.Column("closed_until", TS, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("is_assumption", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("closed_until > closed_from", name="closed_range"),
        sa.CheckConstraint("calendar IN ('fx','xau','boi')", name="calendar"),
        sa.PrimaryKeyConstraint("id", name="pk_market_holidays"),
        sa.UniqueConstraint("calendar", "closed_from", name="uq_market_holiday"),
    )
    op.create_index("ix_market_holidays_calendar", "market_holidays", ["calendar"])
    op.add_column(
        "official_reference_rates",
        sa.Column("attributes_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )

    table = sa.table(
        "market_holidays",
        sa.column("calendar"),
        sa.column("closed_from"),
        sa.column("closed_until"),
        sa.column("name"),
        sa.column("source"),
    )
    rows = []
    for d, name in BOI_REST_DAYS:
        start = datetime.combine(date.fromisoformat(d), time(0), IL)
        rows.append(
            {
                "calendar": "boi",
                "closed_from": start,
                "closed_until": start + timedelta(days=1),
                "name": name,
                "source": "pyluach-computed Israeli rest day; assumed no BoI publication",
            }
        )
    for d, name in FX_XAU_DAYS:
        end = datetime.combine(date.fromisoformat(d), time(17), NY)
        start = datetime.combine(date.fromisoformat(d) - timedelta(days=1), time(17), NY)
        for cal in ("fx", "xau"):
            rows.append(
                {
                    "calendar": cal,
                    "closed_from": start,
                    "closed_until": end,
                    "name": name,
                    "source": "common FX/spot-metals convention; verify",
                }
            )
    op.bulk_insert(table, rows)

    for symbol, cal in (("USDILS", "fx"), ("XAUUSD", "xau")):
        op.execute(
            sa.text(
                "UPDATE instruments SET configuration_json = jsonb_set(configuration_json, "
                "'{sessions,holiday_calendar}', to_jsonb(CAST(:c AS text))) WHERE symbol = :s"
            ).bindparams(c=cal, s=symbol)
        )


def downgrade() -> None:
    op.execute(
        "UPDATE instruments SET configuration_json = "
        "configuration_json #- '{sessions,holiday_calendar}'"
    )
    op.drop_column("official_reference_rates", "attributes_json")
    op.drop_table("market_holidays")
