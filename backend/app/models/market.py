"""Market data storage. Quotes and candles are TimescaleDB hypertables (migration 0003)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

PRICE = Numeric(24, 10)
VOLUME = Numeric(38, 10)
QUALITY_CHECK = "data_quality_status IN ('verified','suspect','rejected')"


class MarketQuote(Base):
    __tablename__ = "market_quotes"
    __table_args__ = (CheckConstraint(QUALITY_CHECK, name="data_quality_status"),)

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT"), primary_key=True
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("market_providers.id", ondelete="RESTRICT"), primary_key=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bid: Mapped[Decimal | None] = mapped_column(PRICE)
    ask: Mapped[Decimal | None] = mapped_column(PRICE)
    mid: Mapped[Decimal | None] = mapped_column(PRICE)
    last_price: Mapped[Decimal | None] = mapped_column(PRICE)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    data_quality_status: Mapped[str] = mapped_column(String(10), nullable=False)
    quality_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        CheckConstraint(QUALITY_CHECK, name="data_quality_status"),
        CheckConstraint("timeframe IN ('1m','5m','15m','1h','4h','1d')", name="timeframe"),
    )

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT"), primary_key=True
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("market_providers.id", ondelete="RESTRICT"), primary_key=True
    )
    timeframe: Mapped[str] = mapped_column(String(3), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    high: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    low: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(VOLUME)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_quality_status: Mapped[str] = mapped_column(String(10), nullable=False)
    quality_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # NULL = provider bar. 'derived:1h' = built locally from verified 1h bars.
    derived_from: Mapped[str | None] = mapped_column(String(20))


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"
    __table_args__ = (
        CheckConstraint("severity IN ('reject','suspect','info')", name="severity"),
        Index("ix_dq_events_instrument_detected", "instrument_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT")
    )
    provider_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("market_providers.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class OfficialReferenceRate(Base):
    """Published reference rates (e.g. BoI representative rate). Not executable prices."""

    __tablename__ = "official_reference_rates"
    __table_args__ = (
        UniqueConstraint("instrument_id", "provider_id", "rate_date", name="uq_reference_rate"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("market_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
