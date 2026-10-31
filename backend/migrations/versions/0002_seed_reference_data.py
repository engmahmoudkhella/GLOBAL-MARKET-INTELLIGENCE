"""Seed instruments, providers and provider symbol mappings (configuration only, no prices).

Values are literal snapshots so this migration never changes when application code does.

Revision ID: 0002_seed_reference_data
Revises: 0001_foundation
Create Date: 2026-10-31
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0002_seed_reference_data"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

V1_HORIZONS = ["1h", "4h", "24h", "7d", "30d"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

# Session calendars are PROVISIONAL placeholders following common market convention
# (FX: Sun 17:00 - Fri 17:00 New York; spot gold additionally pauses 17:00-18:00 NY).
# Phase 2 replaces them with provider-defined sessions and holiday data.
INSTRUMENTS = [
    {
        "symbol": "USDILS",
        "display_name": "USD/ILS",
        "asset_class": "forex",
        "base_currency": "USD",
        "quote_currency": "ILS",
        "role": "primary",
        "configuration_json": {
            "schema_version": 1,
            "sessions": {
                "kind": "weekly",
                "timezone": "America/New_York",
                "weekly_open": {"weekday": "sun", "time": "17:00:00"},
                "weekly_close": {"weekday": "fri", "time": "17:00:00"},
                "daily_breaks": [],
                "provisional": True,
            },
            "price_precision": 4,
            "staleness_seconds": 300,
            "max_spread_bps": None,
            "candle_timeframes": TIMEFRAMES,
            "forecasting_enabled": True,
            "forecast_horizons": V1_HORIZONS,
            "notes": "30d horizon required for importer invoice planning.",
        },
    },
    {
        "symbol": "XAUUSD",
        "display_name": "XAU/USD",
        "asset_class": "metal",
        "base_currency": "XAU",
        "quote_currency": "USD",
        "role": "primary",
        "configuration_json": {
            "schema_version": 1,
            "sessions": {
                "kind": "weekly",
                "timezone": "America/New_York",
                "weekly_open": {"weekday": "sun", "time": "18:00:00"},
                "weekly_close": {"weekday": "fri", "time": "17:00:00"},
                "daily_breaks": [{"start": "17:00:00", "end": "18:00:00"}],
                "provisional": True,
            },
            "price_precision": 2,
            "staleness_seconds": 300,
            "max_spread_bps": None,
            "candle_timeframes": TIMEFRAMES,
            "forecasting_enabled": True,
            "forecast_horizons": V1_HORIZONS,
            "notes": None,
        },
    },
    {
        "symbol": "BTCUSD",
        "display_name": "BTC/USD",
        "asset_class": "crypto",
        "base_currency": "BTC",
        "quote_currency": "USD",
        "role": "primary",
        "configuration_json": {
            "schema_version": 1,
            "sessions": {
                "kind": "continuous",
                "timezone": "UTC",
                "daily_breaks": [],
                "provisional": False,
            },
            "price_precision": 2,
            "staleness_seconds": 120,
            "max_spread_bps": None,
            "candle_timeframes": TIMEFRAMES,
            "forecasting_enabled": True,
            "forecast_horizons": V1_HORIZONS,
            "notes": "USD-quoted sources only (Coinbase BTC-USD primary, CoinGecko reference).",
        },
    },
    {
        "symbol": "BTCUSDT",
        "display_name": "BTC/USDT (Binance, secondary)",
        "asset_class": "crypto",
        "base_currency": "BTC",
        "quote_currency": "USDT",
        "role": "secondary",
        "configuration_json": {
            "schema_version": 1,
            "sessions": {
                "kind": "continuous",
                "timezone": "UTC",
                "daily_breaks": [],
                "provisional": False,
            },
            "price_precision": 2,
            "staleness_seconds": 120,
            "max_spread_bps": None,
            "candle_timeframes": TIMEFRAMES,
            "forecasting_enabled": False,
            "forecast_horizons": [],
            "notes": "Separate USDT-quoted series. Never relabelled or merged into BTCUSD.",
        },
    },
]

# capabilities stay empty until an adapter actually implements them (Phase 2).
PROVIDERS = [
    {
        "provider_name": "boi",
        "display_name": "Bank of Israel",
        "provider_type": "official",
        "licence_notes": "Public data; attribution required. Representative rate is a daily "
        "reference, not an executable price.",
        "attribution": "Source: Bank of Israel",
    },
    {
        "provider_name": "twelvedata",
        "display_name": "Twelve Data (Grow, individual)",
        "provider_type": "market_data",
        "licence_notes": "Individual plan: personal, non-commercial use only; no display or "
        "redistribution to third parties. XAU/USD and USD/ILS coverage on Grow "
        "unconfirmed (gates G1/G2).",
        "attribution": "Data: Twelve Data",
    },
    {
        "provider_name": "coinbase",
        "display_name": "Coinbase Exchange (public market data)",
        "provider_type": "exchange",
        "licence_notes": "Coinbase Market Data Terms of Use apply; personal-use wording to be "
        "verified (gate G5).",
        "attribution": "Data: Coinbase Exchange",
    },
    {
        "provider_name": "coingecko",
        "display_name": "CoinGecko (Demo API)",
        "provider_type": "reference",
        "licence_notes": "Demo plan: 30 calls/min, 10,000 calls/month; attribution required.",
        "attribution": "Powered by CoinGecko API",
    },
    {
        "provider_name": "binance",
        "display_name": "Binance (public market data, secondary)",
        "provider_type": "exchange",
        "licence_notes": "Optional secondary BTCUSDT series. EU availability at risk (gate G7).",
        "attribution": "Data: Binance",
    },
]

MAPPINGS = [
    ("USDILS", "twelvedata", "USD/ILS", "primary", 10, "Coverage on Grow unconfirmed (G2)."),
    (
        "USDILS",
        "boi",
        "USD",
        "reference",
        20,
        "BoI representative rate; series identifier to be confirmed in Phase 2. Not executable.",
    ),
    ("XAUUSD", "twelvedata", "XAU/USD", "primary", 10, "Coverage on Grow unconfirmed (G1)."),
    ("BTCUSD", "coinbase", "BTC-USD", "primary", 10, None),
    ("BTCUSD", "coingecko", "bitcoin", "reference", 20, "vs_currency=usd"),
    ("BTCUSDT", "binance", "BTCUSDT", "primary", 10, "USDT-quoted. Never relabel as USD."),
]


def upgrade() -> None:
    conn = op.get_bind()
    for i in INSTRUMENTS:
        conn.execute(
            sa.text("""INSERT INTO instruments
                (symbol, display_name, asset_class, base_currency, quote_currency, role,
                 configuration_json)
                VALUES (:symbol, :display_name, :asset_class, :base_currency, :quote_currency,
                        :role, CAST(:cfg AS jsonb))"""),
            {
                **{k: v for k, v in i.items() if k != "configuration_json"},
                "cfg": json.dumps(i["configuration_json"]),
            },
        )
    for p in PROVIDERS:
        conn.execute(
            sa.text("""INSERT INTO market_providers
                (provider_name, display_name, provider_type, licence_notes, attribution)
                VALUES (:provider_name, :display_name, :provider_type, :licence_notes,
                        :attribution)"""),
            p,
        )
    for sym, prov, psym, purpose, prio, notes in MAPPINGS:
        conn.execute(
            sa.text("""INSERT INTO instrument_provider_symbols
                (instrument_id, provider_id, provider_symbol, purpose, priority, notes)
                SELECT i.id, p.id, :psym, :purpose, :prio, :notes
                FROM instruments i, market_providers p
                WHERE i.symbol = :sym AND p.provider_name = :prov"""),
            {
                "sym": sym,
                "prov": prov,
                "psym": psym,
                "purpose": purpose,
                "prio": prio,
                "notes": notes,
            },
        )


def downgrade() -> None:
    op.execute("DELETE FROM instrument_provider_symbols")
    op.execute("DELETE FROM market_providers")
    op.execute("DELETE FROM instruments")
