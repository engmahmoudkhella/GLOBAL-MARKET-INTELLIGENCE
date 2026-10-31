"""USD/ILS cross-check: Twelve Data price near BoI publication vs the BoI representative rate.

For a business day with a stored BoI rate, take the verified Twelve Data USDILS quote nearest the
publication time (within +/- GMI_BOI_CROSSCHECK_WINDOW_MINUTES; mid if available, else last).
If none exists, fall back to the nearest verified complete 1m candle close in the same window.
If |TD - BoI| / BoI exceeds GMI_BOI_CROSSCHECK_THRESHOLD_PCT, a `reference_divergence`
data-quality event is recorded. The BoI rate is a reference; a divergence flags data to review,
it does not mark either source wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import get_settings
from app.ingestion.service import _event, resolve
from app.models import MarketCandle, MarketQuote, OfficialReferenceRate
from app.quality.rules import IssueType, QualityIssue

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
Status = Literal["ok", "diverged", "no_market_price", "no_reference"]


@dataclass(frozen=True)
class CrossCheck:
    rate_date: date
    status: Status
    reference_rate: Decimal | None = None
    reference_time: datetime | None = None
    market_price: Decimal | None = None
    market_observed_at: datetime | None = None
    market_source: str | None = None
    diff_pct: Decimal | None = None


def crosscheck_boi(
    session: Session,
    rate_date: date,
    *,
    symbol: str = "USDILS",
    threshold_pct: Decimal | None = None,
    window_minutes: int | None = None,
) -> CrossCheck:
    s = get_settings()
    threshold = threshold_pct if threshold_pct is not None else s.boi_crosscheck_threshold_pct
    window = timedelta(minutes=window_minutes or s.boi_crosscheck_window_minutes)
    boi = resolve(session, symbol, "boi")
    td = resolve(session, symbol, "twelvedata")
    ref = session.scalar(
        select(OfficialReferenceRate).where(
            OfficialReferenceRate.instrument_id == boi.instrument.id,
            OfficialReferenceRate.provider_id == boi.provider.id,
            OfficialReferenceRate.rate_date == rate_date,
        )
    )
    if ref is None:
        return CrossCheck(rate_date, "no_reference")
    ref_time = ref.published_at or datetime.combine(
        rate_date, s.boi_publication_fallback_time, ISRAEL_TZ
    )
    lo, hi = ref_time - window, ref_time + window

    price: Decimal | None = None
    observed: datetime | None = None
    source: str | None = None
    q = session.scalar(
        select(MarketQuote)
        .where(
            MarketQuote.instrument_id == td.instrument.id,
            MarketQuote.provider_id == td.provider.id,
            MarketQuote.data_quality_status == "verified",
            MarketQuote.observed_at >= lo,
            MarketQuote.observed_at <= hi,
        )
        .order_by(
            func.abs(
                func.extract("epoch", MarketQuote.observed_at)
                - func.extract("epoch", literal(ref_time))
            )
        )
        .limit(1)
    )
    if q is not None:
        price = q.mid if q.mid is not None else q.last_price
        observed, source = q.observed_at, "quote:" + ("mid" if q.mid is not None else "last")
    else:
        c = session.scalar(
            select(MarketCandle)
            .where(
                MarketCandle.instrument_id == td.instrument.id,
                MarketCandle.provider_id == td.provider.id,
                MarketCandle.timeframe == "1m",
                MarketCandle.data_quality_status == "verified",
                MarketCandle.is_complete.is_(True),
                MarketCandle.open_time >= lo,
                MarketCandle.open_time <= hi,
            )
            .order_by(
                func.abs(
                    func.extract("epoch", MarketCandle.close_time)
                    - func.extract("epoch", literal(ref_time))
                )
            )
            .limit(1)
        )
        if c is not None:
            price, observed, source = c.close, c.close_time, "candle:1m_close"
    if price is None:
        return CrossCheck(rate_date, "no_market_price", ref.rate, ref_time)

    diff = (abs(price - ref.rate) / ref.rate * 100).quantize(Decimal("0.0001"))
    status: Status = "diverged" if diff > threshold else "ok"
    if status == "diverged":
        _event(
            session,
            QualityIssue(
                IssueType.REFERENCE_DIVERGENCE,
                "suspect",
                f"Twelve Data USD/ILS differs from BoI representative rate by {diff}%",
                observed,
                {
                    "rate_date": rate_date.isoformat(),
                    "boi_rate": ref.rate,
                    "market_price": price,
                    "market_source": source,
                    "reference_time": ref_time.isoformat(),
                    "threshold_pct": threshold,
                    "diff_pct": diff,
                },
            ),
            instrument_id=td.instrument.id,
            provider_id=td.provider.id,
            now=utcnow(),
        )
        session.commit()
    return CrossCheck(rate_date, status, ref.rate, ref_time, price, observed, source, diff)


@dataclass(frozen=True)
class QuoteCrossCheck:
    status: Literal["ok", "diverged", "no_primary_price", "no_reference_price"]
    reference_price: Decimal | None = None
    primary_price: Decimal | None = None
    diff_pct: Decimal | None = None


def crosscheck_reference_quote(
    session: Session,
    symbol: str,
    reference_provider: str,
    *,
    threshold_pct: Decimal | None = None,
    window_seconds: int | None = None,
) -> QuoteCrossCheck:
    """Compare the newest verified reference quote (e.g. CoinGecko) with the nearest verified
    primary quote (e.g. Coinbase mid) within +/- window. Divergence above the threshold is
    recorded as `reference_divergence`; neither source is overwritten."""
    s = get_settings()
    threshold = threshold_pct if threshold_pct is not None else s.coingecko_crosscheck_threshold_pct
    window = timedelta(seconds=window_seconds or s.coingecko_crosscheck_window_seconds)
    ref = resolve(session, symbol, reference_provider)
    ref_q = session.scalar(
        select(MarketQuote)
        .where(
            MarketQuote.instrument_id == ref.instrument.id,
            MarketQuote.provider_id == ref.provider.id,
            MarketQuote.data_quality_status == "verified",
        )
        .order_by(MarketQuote.observed_at.desc())
        .limit(1)
    )
    if ref_q is None or ref_q.last_price is None:
        return QuoteCrossCheck("no_reference_price")
    from app.models import InstrumentProviderSymbol

    primary_id = session.scalar(
        select(InstrumentProviderSymbol.provider_id).where(
            InstrumentProviderSymbol.instrument_id == ref.instrument.id,
            InstrumentProviderSymbol.purpose == "primary",
        )
    )
    at = ref_q.observed_at
    p = session.scalar(
        select(MarketQuote)
        .where(
            MarketQuote.instrument_id == ref.instrument.id,
            MarketQuote.provider_id == primary_id,
            MarketQuote.data_quality_status == "verified",
            MarketQuote.observed_at >= at - window,
            MarketQuote.observed_at <= at + window,
        )
        .order_by(
            func.abs(
                func.extract("epoch", MarketQuote.observed_at) - func.extract("epoch", literal(at))
            )
        )
        .limit(1)
    )
    if p is None:
        return QuoteCrossCheck("no_primary_price", ref_q.last_price)
    primary_price = p.mid if p.mid is not None else p.last_price
    assert primary_price is not None
    diff = (abs(ref_q.last_price - primary_price) / primary_price * 100).quantize(Decimal("0.0001"))
    if diff <= threshold:
        return QuoteCrossCheck("ok", ref_q.last_price, primary_price, diff)
    _event(
        session,
        QualityIssue(
            IssueType.REFERENCE_DIVERGENCE,
            "suspect",
            f"{reference_provider} {symbol} differs from the primary source by {diff}%",
            at,
            {
                "reference_provider": reference_provider,
                "reference_price": ref_q.last_price,
                "primary_price": primary_price,
                "threshold_pct": threshold,
                "diff_pct": diff,
            },
        ),
        instrument_id=ref.instrument.id,
        provider_id=ref.provider.id,
        now=utcnow(),
    )
    session.commit()
    return QuoteCrossCheck("diverged", ref_q.last_price, primary_price, diff)
