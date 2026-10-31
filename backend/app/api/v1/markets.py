from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.core.clock import utcnow
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.ingestion import service
from app.markets.schemas import (
    CandleList,
    CandleOut,
    ExcludedQuoteOut,
    QuoteOut,
    ReferenceRateList,
    ReferenceRateOut,
)
from app.models import (
    Instrument,
    InstrumentProviderSymbol,
    MarketCandle,
    MarketProvider,
    MarketQuote,
    OfficialReferenceRate,
)

router = APIRouter(prefix="/markets", tags=["markets"], dependencies=[Depends(current_user)])

MAX_CANDLES = 2000


class BadRange(AppError):
    status_code, code, title = 422, "bad_range", "Invalid time range"


def _instrument(db: Session, symbol: str) -> Instrument:
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if inst is None:
        raise NotFound(f"Unknown instrument '{symbol}'")
    return inst


def _provider(
    db: Session, inst: Instrument, purpose: str | None, name: str | None
) -> MarketProvider:
    stmt = (
        select(MarketProvider)
        .join(InstrumentProviderSymbol, InstrumentProviderSymbol.provider_id == MarketProvider.id)
        .where(InstrumentProviderSymbol.instrument_id == inst.id)
        .order_by(InstrumentProviderSymbol.priority)
    )
    if name:
        stmt = stmt.where(MarketProvider.provider_name == name)
    elif purpose:
        stmt = stmt.where(InstrumentProviderSymbol.purpose == purpose)
    prov = db.scalars(stmt).first()
    if prov is None:
        raise NotFound(f"No {name or purpose} provider mapped to {inst.symbol}")
    return prov


@router.get("/{symbol}/quote", response_model=QuoteOut)
def quote(symbol: str, db: Session = Depends(get_db)) -> QuoteOut:
    """Latest *verified* quote from the primary provider, with freshness. Never estimated."""
    inst = _instrument(db, symbol)
    now = utcnow()
    f = service.freshness(db, inst.symbol, now)
    out = QuoteOut(
        symbol=inst.symbol,
        provider=f.provider,
        data_status=f.status,
        signals_allowed=f.status == "fresh",
    )
    prov = _provider(db, inst, "primary", None)
    newest = db.scalar(
        select(MarketQuote)
        .where(MarketQuote.instrument_id == inst.id, MarketQuote.provider_id == prov.id)
        .order_by(MarketQuote.observed_at.desc())
        .limit(1)
    )
    if newest is not None and newest.data_quality_status != "verified":
        price = newest.mid if newest.mid is not None else newest.last_price
        out.latest_excluded = ExcludedQuoteOut(
            price=price,
            price_type=None if price is None else ("mid" if newest.mid is not None else "last"),
            observed_at=newest.observed_at,
            data_quality_status=newest.data_quality_status,
            reasons=[str(i.get("type")) for i in newest.quality_issues],
        )
    if f.last_observed_at is None:
        return out
    row = db.scalar(
        select(MarketQuote).where(
            MarketQuote.instrument_id == inst.id,
            MarketQuote.provider_id == prov.id,
            MarketQuote.observed_at == f.last_observed_at,
        )
    )
    assert row is not None
    out.bid, out.ask, out.mid, out.last_price = row.bid, row.ask, row.mid, row.last_price
    out.price_type = "mid" if row.mid is not None else "last"
    out.observed_at, out.received_at = row.observed_at, row.received_at
    out.age_seconds = f.age_seconds
    out.data_quality_status = row.data_quality_status
    return out


@router.get("/{symbol}/candles", response_model=CandleList)
def candles(
    symbol: str,
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "1h",
    start: datetime | None = None,
    end: datetime | None = None,
    provider: str | None = Query(None, description="Defaults to the primary provider"),
    include_rejected: bool = False,
    limit: int = Query(500, ge=1, le=MAX_CANDLES),
    db: Session = Depends(get_db),
) -> CandleList:
    inst = _instrument(db, symbol)
    prov = _provider(db, inst, "primary", provider)
    end = end or utcnow()
    start = start or end - timedelta(days=7)
    if start.tzinfo is None or end.tzinfo is None:
        raise BadRange("start and end must include a timezone (UTC recommended)")
    if start >= end:
        raise BadRange("start must be before end")
    stmt = (
        select(MarketCandle)
        .where(
            MarketCandle.instrument_id == inst.id,
            MarketCandle.provider_id == prov.id,
            MarketCandle.timeframe == timeframe,
            MarketCandle.open_time >= start,
            MarketCandle.open_time < end,
        )
        .order_by(MarketCandle.open_time.desc())
        .limit(limit)
    )
    if not include_rejected:
        stmt = stmt.where(MarketCandle.data_quality_status != "rejected")
    rows = list(reversed(db.scalars(stmt).all()))
    items = [
        CandleOut(
            open_time=r.open_time,
            close_time=r.close_time,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
            is_complete=r.is_complete,
            data_quality_status=r.data_quality_status,
        )
        for r in rows
    ]
    return CandleList(
        symbol=inst.symbol,
        provider=prov.provider_name,
        timeframe=timeframe,
        items=items,
        count=len(items),
    )


@router.get("/{symbol}/reference-rates", response_model=ReferenceRateList)
def reference_rates(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> ReferenceRateList:
    inst = _instrument(db, symbol)
    prov = _provider(db, inst, "reference", "boi" if inst.symbol == "USDILS" else None)
    end = end or utcnow().date()
    start = start or end - timedelta(days=30)
    rows = db.scalars(
        select(OfficialReferenceRate)
        .where(
            OfficialReferenceRate.instrument_id == inst.id,
            OfficialReferenceRate.provider_id == prov.id,
            OfficialReferenceRate.rate_date >= start,
            OfficialReferenceRate.rate_date <= end,
        )
        .order_by(OfficialReferenceRate.rate_date)
    )
    return ReferenceRateList(
        symbol=inst.symbol,
        provider=prov.provider_name,
        note="Official reference rate published once per business day. Not an executable price.",
        items=[
            ReferenceRateOut(
                rate_date=r.rate_date,
                rate=r.rate,
                published_at=r.published_at,
                received_at=r.received_at,
            )
            for r in rows
        ],
    )
