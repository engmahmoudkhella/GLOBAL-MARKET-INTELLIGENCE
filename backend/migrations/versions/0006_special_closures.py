"""Special closures, explained gap events, BoI publication observations, reduced-liquidity days.

* special_closures: manual, non-algorithmic closures (election days, one-off government
  holidays) with date, calendar key, reason and source URL. Seed: 2026-10-27 Knesset election
  day (statutory day off, Basic Law: The Knesset s.10) for the BoI calendar.
* data_quality_events: explanation_status / explanation / explained_at. Events are never
  deleted; an explained event keeps its original fields. The existing missing_reference event
  for 2026-10-27 is reclassified "explained: holiday".
* market_holidays.kind: 'closure' (market closed) or 'reduced_liquidity' (not a closure).
  Seed: Good Friday and Easter Monday 2027/2028 for XAUUSD (London bullion holidays) as
  reduced liquidity / possible closure, ASSUMPTION to verify on 2027-03-26.
* boi_publication_observations: every distinct BoI lastUpdate observed (to learn the real
  publication time before changing the fallback).

Revision ID: 0006_special_closures
Revises: 0005_holidays_reference_attrs
Create Date: 2026-10-31
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "0006_special_closures"
down_revision = "0005_holidays_reference_attrs"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
NY = ZoneInfo("America/New_York")

SPECIAL = [
    (
        "boi",
        "2026-10-27",
        "Knesset election day - statutory day off (Basic Law: The Knesset, section 10)",
        "https://www.shibolet.com/?p=27864",
    ),
]
# Easter dates computed with the anonymous Gregorian algorithm (2027-03-28, 2028-04-16).
XAU_REDUCED = [
    ("2027-03-26", "Good Friday"),
    ("2027-03-29", "Easter Monday"),
    ("2028-04-14", "Good Friday"),
    ("2028-04-17", "Easter Monday"),
]

EXPLAIN_SQL = """
UPDATE data_quality_events e
   SET explanation_status = 'explained',
       explanation = 'holiday: ' || s.reason,
       explained_at = now()
  FROM special_closures s, market_providers p
 WHERE e.event_type = 'missing_reference'
   AND e.explanation_status IS NULL
   AND p.id = e.provider_id AND p.provider_name = 'boi'
   AND s.calendar = 'boi'
   AND e.details_json ->> 'rate_date' = to_char(s.closure_date, 'YYYY-MM-DD')
"""


def upgrade() -> None:
    op.create_table(
        "special_closures",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("calendar", sa.String(20), nullable=False),
        sa.Column("closure_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("calendar IN ('fx','xau','boi')", name="calendar"),
        sa.CheckConstraint("source_url LIKE 'http%'", name="source_url"),
        sa.PrimaryKeyConstraint("id", name="pk_special_closures"),
        sa.UniqueConstraint("calendar", "closure_date", name="uq_special_closure"),
    )
    op.bulk_insert(
        sa.table(
            "special_closures",
            sa.column("calendar"),
            sa.column("closure_date"),
            sa.column("reason"),
            sa.column("source_url"),
        ),
        [
            {"calendar": c, "closure_date": date.fromisoformat(d), "reason": r, "source_url": u}
            for c, d, r, u in SPECIAL
        ],
    )

    op.add_column("data_quality_events", sa.Column("explanation_status", sa.String(20)))
    op.add_column("data_quality_events", sa.Column("explanation", sa.Text()))
    op.add_column("data_quality_events", sa.Column("explained_at", TS))
    op.create_check_constraint(
        "explanation_status", "data_quality_events", "explanation_status IN ('explained')"
    )
    op.execute(EXPLAIN_SQL)

    op.add_column(
        "market_holidays",
        sa.Column("kind", sa.String(20), server_default="closure", nullable=False),
    )
    op.create_check_constraint("kind", "market_holidays", "kind IN ('closure','reduced_liquidity')")
    rows = []
    for d, name in XAU_REDUCED:
        end = datetime.combine(date.fromisoformat(d), time(17), NY)
        rows.append(
            {
                "calendar": "xau",
                "closed_from": end - timedelta(days=1),
                "closed_until": end,
                "name": name,
                "kind": "reduced_liquidity",
                "source": "London bullion market holiday; reduced liquidity / possible "
                "closure - ASSUMPTION, verify against Twelve Data on 2027-03-26",
            }
        )
    op.bulk_insert(
        sa.table(
            "market_holidays",
            sa.column("calendar"),
            sa.column("closed_from"),
            sa.column("closed_until"),
            sa.column("name"),
            sa.column("kind"),
            sa.column("source"),
        ),
        rows,
    )

    op.create_table(
        "boi_publication_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("published_at", TS, nullable=False),
        sa.Column("first_observed_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_boi_publication_observations"),
        sa.UniqueConstraint("rate_date", "published_at", name="uq_boi_publication_observation"),
    )


def downgrade() -> None:
    op.drop_table("boi_publication_observations")
    op.execute("DELETE FROM market_holidays WHERE kind = 'reduced_liquidity'")
    op.drop_constraint("ck_market_holidays_kind", "market_holidays")
    op.drop_column("market_holidays", "kind")
    op.drop_constraint("ck_data_quality_events_explanation_status", "data_quality_events")
    op.drop_column("data_quality_events", "explained_at")
    op.drop_column("data_quality_events", "explanation")
    op.drop_column("data_quality_events", "explanation_status")
    op.drop_table("special_closures")
