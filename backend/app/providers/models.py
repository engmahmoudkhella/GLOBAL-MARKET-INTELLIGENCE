"""Normalized provider outputs. Prices are Decimal, timestamps timezone-aware UTC.

These are *observations* returned by a provider. Nothing here is ever synthesized: a field the
provider did not supply is None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d"]

TIMEFRAME_DELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


class Capability(StrEnum):
    LATEST_QUOTE = "latest_quote"
    HISTORICAL_OHLCV = "historical_ohlcv"
    INTRADAY_OHLCV = "intraday_ohlcv"
    ORDER_BOOK = "order_book"
    MARKET_STATUS = "market_status"
    PROVIDER_STATUS = "provider_status"
    REFERENCE_RATE = "reference_rate"
    # Optional SRS §5.1 capabilities (no adapter implements them yet)
    FUNDING_RATES = "funding_rates"
    OPEN_INTEREST = "open_interest"
    LIQUIDATIONS = "liquidations"
    MARKET_FLOWS = "market_flows"
    ONCHAIN_METRICS = "onchain_metrics"


@dataclass(frozen=True)
class Quote:
    provider_symbol: str
    observed_at: datetime
    received_at: datetime
    bid: Decimal | None = None
    ask: Decimal | None = None
    last_price: Decimal | None = None

    @property
    def mid(self) -> Decimal | None:
        if self.bid is None or self.ask is None:
            return None
        return (self.bid + self.ask) / 2

    @property
    def latency_ms(self) -> int:
        return max(0, int((self.received_at - self.observed_at).total_seconds() * 1000))


@dataclass(frozen=True)
class Candle:
    provider_symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    received_at: datetime
    is_complete: bool

    @property
    def close_time(self) -> datetime:
        return self.open_time + TIMEFRAME_DELTA[self.timeframe]


@dataclass(frozen=True)
class OrderBookLevel:
    price: Decimal
    size: Decimal


@dataclass(frozen=True)
class OrderBook:
    provider_symbol: str
    observed_at: datetime | None  # None when the provider does not timestamp the book
    received_at: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]


MarketState = Literal["open", "closed", "halted", "unknown"]


@dataclass(frozen=True)
class MarketStatus:
    provider_symbol: str
    status: MarketState
    detail: str | None
    checked_at: datetime


@dataclass(frozen=True)
class ProviderStatus:
    ok: bool
    checked_at: datetime
    latency_ms: int | None
    server_time: datetime | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ReferenceRate:
    """An official published reference rate (e.g. Bank of Israel representative rate).

    Not an executable price and never stored as a market quote.
    """

    provider_symbol: str
    rate_date: date
    rate: Decimal
    received_at: datetime
    published_at: datetime | None = None
    extra: dict[str, str] = field(default_factory=dict)
