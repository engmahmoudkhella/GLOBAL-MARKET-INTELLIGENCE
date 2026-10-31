from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

# Prices are serialized as strings so no precision is lost to JSON floats.
Price = Annotated[Decimal, PlainSerializer(lambda d: format(d, "f"), return_type=str)]


class ExcludedQuoteOut(BaseModel):
    """Newest stored quote that failed quality checks (e.g. outside the trading session).

    Shown for transparency only; never used by indicators, candles, forecasts or evaluation."""

    price: Price | None
    price_type: Literal["mid", "last"] | None
    observed_at: datetime
    data_quality_status: str
    reasons: list[str]


class QuoteOut(BaseModel):
    symbol: str
    provider: str | None
    data_status: Literal["fresh", "stale", "market_closed", "no_data"]
    signals_allowed: bool
    bid: Price | None = None
    ask: Price | None = None
    mid: Price | None = None
    last_price: Price | None = None
    price_type: Literal["mid", "last"] | None = None
    observed_at: datetime | None = None
    received_at: datetime | None = None
    age_seconds: float | None = None
    data_quality_status: str | None = None
    latest_excluded: ExcludedQuoteOut | None = None


class CandleOut(BaseModel):
    open_time: datetime
    close_time: datetime
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Price | None
    is_complete: bool
    data_quality_status: str


class CandleList(BaseModel):
    symbol: str
    provider: str
    timeframe: str
    items: list[CandleOut]
    count: int


class ReferenceRateOut(BaseModel):
    rate_date: date
    rate: Price
    published_at: datetime | None
    received_at: datetime


class ReferenceRateList(BaseModel):
    symbol: str
    provider: str
    note: str
    items: list[ReferenceRateOut]
