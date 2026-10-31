from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("asset_class IN ('forex','metal','crypto')", name="asset_class"),
        CheckConstraint("role IN ('primary','secondary')", name="role"),
        CheckConstraint(
            "market_status IN ('unknown','open','closed','halted')", name="market_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(10), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, server_default="primary")
    market_status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="unknown")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class MarketProvider(TimestampMixin, Base):
    __tablename__ = "market_providers"
    __table_args__ = (
        CheckConstraint(
            "provider_type IN ('official','market_data','exchange','reference','economic','news')",
            name="provider_type",
        ),
        CheckConstraint(
            "status IN ('not_configured','active','degraded','down','disabled')", name="status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="not_configured")
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    licence_notes: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class InstrumentProviderSymbol(Base):
    __tablename__ = "instrument_provider_symbols"
    __table_args__ = (
        UniqueConstraint("instrument_id", "provider_id", name="uq_instrument_provider"),
        CheckConstraint("purpose IN ('primary','reference','secondary')", name="purpose"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("market_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    notes: Mapped[str | None] = mapped_column(Text)
