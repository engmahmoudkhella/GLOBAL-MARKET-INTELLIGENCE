"""Derived candles and daily session boundaries (owner decision 2026-10-31).

* market_candles.derived_from: NULL for provider bars, 'derived:1h' for locally built 4h/1d bars.
* instruments.configuration_json.daily_candle_boundary: FX/gold 17:00 America/New_York
  (conventional FX day roll), crypto 00:00 UTC.

Revision ID: 0004_derived_candles
Revises: 0003_market_data
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_derived_candles"
down_revision = "0003_market_data"
branch_labels = None
depends_on = None

BOUNDARIES = {
    "USDILS": ("America/New_York", "17:00:00"),
    "XAUUSD": ("America/New_York", "17:00:00"),
    "BTCUSD": ("UTC", "00:00:00"),
    "BTCUSDT": ("UTC", "00:00:00"),
}


def upgrade() -> None:
    op.add_column("market_candles", sa.Column("derived_from", sa.String(20), nullable=True))
    for symbol, (tz, t) in BOUNDARIES.items():
        op.execute(
            sa.text(
                "UPDATE instruments SET configuration_json = jsonb_set(configuration_json, "
                "'{daily_candle_boundary}', jsonb_build_object('timezone', CAST(:tz AS text), "
                "'time', CAST(:t AS text))) WHERE symbol = :s"
            ).bindparams(tz=tz, t=t, s=symbol)
        )


def downgrade() -> None:
    op.execute(
        "UPDATE instruments SET configuration_json = configuration_json - 'daily_candle_boundary'"
    )
    op.drop_column("market_candles", "derived_from")
