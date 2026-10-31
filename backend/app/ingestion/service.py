"""Ingestion: provider -> validation -> storage, with provider health bookkeeping.

Rules: nothing is filled or estimated; every stored row keeps provider, observed and received
timestamps and its quality status; completed candles are never overwritten; provider failures
are recorded and never crash the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.instruments.config_schema import InstrumentConfig
from app.markets.sessions import MarketCalendar
from app.models import (
    DataQualityEvent,
    Instrument,
    InstrumentProviderSymbol,
    MarketCandle,
    MarketProvider,
    MarketQuote,
    OfficialReferenceRate,
)
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderError
from app.providers.models import TIMEFRAME_DELTA, Candle, Timeframe
from app.quality import rules
from app.quality.rules import IssueType, QualityIssue

log = logging.getLogger(__name__)

DOWN_AFTER_FAILURES = 5
HISTORY_WINDOW = 100
T = TypeVar("T")


@dataclass(frozen=True)
class Target:
    instrument: Instrument
    provider: MarketProvider
    provider_symbol: str
    config: InstrumentConfig
    calendar: MarketCalendar


@dataclass
class IngestResult:
    ok: bool
    stored: int = 0
    skipped: int = 0
    statuses: dict[str, int] = field(default_factory=dict)
    issues: int = 0
    error: str | None = None

    def count(self, status: str) -> None:
        self.statuses[status] = self.statuses.get(status, 0) + 1


def resolve(session: Session, symbol: str, provider_name: str) -> Target:
    row = session.execute(
        select(Instrument, MarketProvider, InstrumentProviderSymbol)
        .join(InstrumentProviderSymbol, InstrumentProviderSymbol.instrument_id == Instrument.id)
        .join(MarketProvider, MarketProvider.id == InstrumentProviderSymbol.provider_id)
        .where(Instrument.symbol == symbol, MarketProvider.provider_name == provider_name)
    ).first()
    if row is None:
        raise LookupError(f"{provider_name} is not mapped to {symbol}")
    inst, prov, mapping = row
    cfg = InstrumentConfig.model_validate(inst.configuration_json)
    return Target(inst, prov, mapping.provider_symbol, cfg, MarketCalendar(cfg.sessions))


# ------------------------------------------------------------------ provider health
def _event(
    session: Session,
    issue: QualityIssue,
    *,
    instrument_id: int | None,
    provider_id: int | None,
    now: datetime,
) -> None:
    details = issue.as_json()["details"]
    session.add(
        DataQualityEvent(
            instrument_id=instrument_id,
            provider_id=provider_id,
            event_type=issue.type.value,
            severity=issue.severity,
            message=issue.message[:500],
            detected_at=now,
            window_start=_parse_dt(details.get("window_start")) or issue.at,
            window_end=_parse_dt(details.get("window_end")),
            details_json=details,
        )
    )


def _parse_dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


@contextmanager
def provider_call(
    session: Session,
    provider: MarketProvider,
    adapter: MarketDataProvider,
    result: IngestResult,
    now: Callable[[], datetime] = utcnow,
) -> Iterator[None]:
    """Run a provider interaction; record success/failure on market_providers."""
    try:
        yield
    except ProviderError as exc:
        session.rollback()
        previous_status = provider.status  # read before the UPDATE below changes it
        failures = provider.consecutive_failures + 1
        new_status = "down" if failures >= DOWN_AFTER_FAILURES else "degraded"
        session.execute(
            update(MarketProvider)
            .where(MarketProvider.id == provider.id)
            .values(consecutive_failures=failures, status=new_status, last_error_at=now())
        )
        if new_status == "down" and previous_status != "down":
            _event(
                session,
                QualityIssue(
                    IssueType.OUTAGE, "suspect", f"provider down after {failures} failures: {exc}"
                ),
                instrument_id=None,
                provider_id=provider.id,
                now=now(),
            )
        session.commit()
        log.warning("provider %s failed (%s): %s", provider.provider_name, new_status, exc)
        result.ok, result.error = False, f"{type(exc).__name__}: {exc}"
        return
    session.execute(
        update(MarketProvider)
        .where(MarketProvider.id == provider.id)
        .values(
            consecutive_failures=0,
            status="active",
            last_success_at=now(),
            capabilities=sorted(c.value for c in adapter.capabilities),
        )
    )
    session.commit()


# ------------------------------------------------------------------ quotes
def _recent_quotes(session: Session, t: Target) -> Sequence[MarketQuote]:
    return list(
        reversed(
            session.scalars(
                select(MarketQuote)
                .where(
                    MarketQuote.instrument_id == t.instrument.id,
                    MarketQuote.provider_id == t.provider.id,
                    MarketQuote.data_quality_status == "verified",
                )
                .order_by(MarketQuote.observed_at.desc())
                .limit(HISTORY_WINDOW)
            ).all()
        )
    )


def ingest_quote(session: Session, symbol: str, adapter: MarketDataProvider) -> IngestResult:
    t = resolve(session, symbol, adapter.name)
    result = IngestResult(ok=True)
    with provider_call(session, t.provider, adapter, result):
        q = adapter.get_latest_quote(t.provider_symbol)
        history = _recent_quotes(session, t)
        spreads = [s for s in (rules.spread_bps(_as_quote(h)) for h in history) if s is not None]
        prices = [p for p in (h.mid or h.last_price for h in history) if p is not None]
        issues = rules.check_quote(q, spreads, t.config.max_spread_bps)
        price = q.mid if q.mid is not None else q.last_price
        if price is not None and not issues:
            issues += rules.check_outlier_return(prices, price, q.observed_at)
        status = rules.status_from(issues)
        # RETURNING (not rowcount, which psycopg reports as -1 here) tells us if a row was written.
        inserted = (
            session.execute(
                insert(MarketQuote)
                .values(
                    instrument_id=t.instrument.id,
                    provider_id=t.provider.id,
                    observed_at=q.observed_at,
                    received_at=q.received_at,
                    bid=q.bid,
                    ask=q.ask,
                    mid=q.mid,
                    last_price=q.last_price,
                    latency_ms=q.latency_ms,
                    data_quality_status=status,
                    quality_issues=[i.as_json() for i in issues],
                )
                .on_conflict_do_nothing()
                .returning(MarketQuote.observed_at)
            ).first()
            is not None
        )
        if inserted:
            result.stored += 1
            result.count(status)
            for i in issues:
                _event(
                    session,
                    i,
                    instrument_id=t.instrument.id,
                    provider_id=t.provider.id,
                    now=q.received_at,
                )
            result.issues += len(issues)
        else:
            result.skipped += 1  # same observation already stored
    return result


def _as_quote(row: MarketQuote) -> Any:
    from app.providers.models import Quote

    return Quote("", row.observed_at, row.received_at, row.bid, row.ask, row.last_price)


# ------------------------------------------------------------------ candles
def ingest_candles(
    session: Session,
    symbol: str,
    adapter: MarketDataProvider,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    *,
    detect_gaps: bool = True,
) -> IngestResult:
    t = resolve(session, symbol, adapter.name)
    result = IngestResult(ok=True)
    with provider_call(session, t.provider, adapter, result):
        candles = adapter.get_intraday_ohlcv(t.provider_symbol, timeframe, start, end)
        prev = [
            c
            for c in session.scalars(
                select(MarketCandle.close)
                .where(
                    MarketCandle.instrument_id == t.instrument.id,
                    MarketCandle.provider_id == t.provider.id,
                    MarketCandle.timeframe == timeframe,
                    MarketCandle.open_time < start,
                    MarketCandle.data_quality_status == "verified",
                )
                .order_by(MarketCandle.open_time.desc())
                .limit(HISTORY_WINDOW)
            ).all()
        ][::-1]
        dup_times = {i.at for i in rules.find_duplicates(candles)}
        for c in candles:
            issues = (
                rules.check_ohlc(c)
                + rules.check_alignment(c)
                + rules.check_timestamp(c.open_time, c.received_at)
            )
            if c.open_time in dup_times:
                issues.append(
                    QualityIssue(
                        IssueType.DUPLICATE,
                        "suspect",
                        "provider returned this candle more than once",
                        c.open_time,
                    )
                )
            if not issues and c.is_complete:
                issues += rules.check_outlier_return(prev, c.close, c.open_time)
            status = rules.status_from(issues)
            if _upsert_candle(session, t, c, status, issues):
                result.stored += 1
                result.count(status)
                for i in issues:
                    _event(
                        session,
                        i,
                        instrument_id=t.instrument.id,
                        provider_id=t.provider.id,
                        now=c.received_at,
                    )
                result.issues += len(issues)
            else:
                result.skipped += 1
            if status == "verified" and c.is_complete:
                prev.append(c.close)
        if detect_gaps:
            result.issues += record_gaps(
                session, t, timeframe, start, min(end, _last_complete_bound(timeframe))
            )
    return result


def _last_complete_bound(timeframe: str) -> datetime:
    step = TIMEFRAME_DELTA[timeframe]
    now = utcnow()
    secs = int(step.total_seconds())
    return datetime.fromtimestamp(int(now.timestamp()) // secs * secs, now.tzinfo)


def _upsert_candle(
    session: Session, t: Target, c: Candle, status: str, issues: list[QualityIssue]
) -> bool:
    """Insert, or replace an *incomplete* stored candle. Completed candles are immutable."""
    values: dict[str, Any] = dict(
        instrument_id=t.instrument.id,
        provider_id=t.provider.id,
        timeframe=c.timeframe,
        open_time=c.open_time,
        close_time=c.close_time,
        open=c.open,
        high=c.high,
        low=c.low,
        close=c.close,
        volume=c.volume,
        is_complete=c.is_complete,
        received_at=c.received_at,
        data_quality_status=status,
        quality_issues=[i.as_json() for i in issues],
    )
    base = insert(MarketCandle).values(**values)
    stmt = base.on_conflict_do_update(
        index_elements=["instrument_id", "provider_id", "timeframe", "open_time"],
        set_={
            k: base.excluded[k]
            for k in values
            if k not in ("instrument_id", "provider_id", "timeframe", "open_time")
        },
        where=MarketCandle.is_complete.is_(False),
    ).returning(MarketCandle.open_time)
    return session.execute(stmt).first() is not None


def record_gaps(session: Session, t: Target, timeframe: str, start: datetime, end: datetime) -> int:
    if end <= start:
        return 0
    times = session.scalars(
        select(MarketCandle.open_time).where(
            MarketCandle.instrument_id == t.instrument.id,
            MarketCandle.provider_id == t.provider.id,
            MarketCandle.timeframe == timeframe,
            MarketCandle.open_time >= start,
            MarketCandle.open_time < end,
            MarketCandle.data_quality_status != "rejected",
        )
    ).all()
    gaps = rules.find_missing_candles(times, timeframe, start, end, t.calendar)
    new = 0
    for g in gaps:
        ws = _parse_dt(g.details["window_start"])
        we = _parse_dt(g.details["window_end"])
        exists = session.scalar(
            select(DataQualityEvent.id)
            .where(
                and_(
                    DataQualityEvent.instrument_id == t.instrument.id,
                    DataQualityEvent.provider_id == t.provider.id,
                    DataQualityEvent.event_type == IssueType.MISSING_CANDLE.value,
                    DataQualityEvent.window_start == ws,
                    DataQualityEvent.window_end == we,
                    DataQualityEvent.details_json["timeframe"].astext == timeframe,
                )
            )
            .limit(1)
        )
        if exists is None:
            issue = QualityIssue(
                g.type, g.severity, g.message, g.at, {**g.details, "timeframe": timeframe}
            )
            _event(
                session,
                issue,
                instrument_id=t.instrument.id,
                provider_id=t.provider.id,
                now=utcnow(),
            )
            new += 1
    return new


# ------------------------------------------------------------------ reference rates
def ingest_reference_rates(
    session: Session,
    symbol: str,
    adapter: MarketDataProvider,
    start: date,
    end: date,
    *,
    include_latest: bool = True,
) -> IngestResult:
    t = resolve(session, symbol, adapter.name)
    result = IngestResult(ok=True)
    with provider_call(session, t.provider, adapter, result):
        rates = list(adapter.get_reference_rates(t.provider_symbol, start, end))
        latest_fn = getattr(adapter, "get_latest_reference_rate", None)
        if include_latest and latest_fn is not None:
            rates.append(latest_fn(t.provider_symbol))
        for r in rates:
            existing = session.scalar(
                select(OfficialReferenceRate).where(
                    OfficialReferenceRate.instrument_id == t.instrument.id,
                    OfficialReferenceRate.provider_id == t.provider.id,
                    OfficialReferenceRate.rate_date == r.rate_date,
                )
            )
            if existing is None:
                session.add(
                    OfficialReferenceRate(
                        instrument_id=t.instrument.id,
                        provider_id=t.provider.id,
                        rate_date=r.rate_date,
                        rate=r.rate,
                        published_at=r.published_at,
                        received_at=r.received_at,
                    )
                )
                session.flush()
                result.stored += 1
            elif existing.rate != r.rate:
                # Official values are not silently revised: keep the first, record the conflict.
                _event(
                    session,
                    QualityIssue(
                        IssueType.DUPLICATE,
                        "suspect",
                        "reference rate differs from stored value",
                        None,
                        {
                            "rate_date": r.rate_date.isoformat(),
                            "stored": existing.rate,
                            "received": r.rate,
                        },
                    ),
                    instrument_id=t.instrument.id,
                    provider_id=t.provider.id,
                    now=r.received_at,
                )
                result.issues += 1
                result.skipped += 1
            else:
                if existing.published_at is None and r.published_at is not None:
                    existing.published_at = r.published_at
                result.skipped += 1
    return result


# ------------------------------------------------------------------ freshness
@dataclass(frozen=True)
class Freshness:
    symbol: str
    provider: str | None
    status: rules.DataStatus
    last_observed_at: datetime | None
    age_seconds: float | None


def freshness(session: Session, symbol: str, now: datetime | None = None) -> Freshness:
    now = now or utcnow()
    inst = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if inst is None:
        raise LookupError(symbol)
    cfg = InstrumentConfig.model_validate(inst.configuration_json)
    primary = (
        session.execute(
            select(MarketProvider)
            .join(
                InstrumentProviderSymbol, InstrumentProviderSymbol.provider_id == MarketProvider.id
            )
            .where(
                InstrumentProviderSymbol.instrument_id == inst.id,
                InstrumentProviderSymbol.purpose == "primary",
            )
        )
        .scalars()
        .first()
    )
    last = None
    if primary is not None:
        last = session.scalar(
            select(MarketQuote.observed_at)
            .where(
                MarketQuote.instrument_id == inst.id,
                MarketQuote.provider_id == primary.id,
                MarketQuote.data_quality_status == "verified",
            )
            .order_by(MarketQuote.observed_at.desc())
            .limit(1)
        )
    status = rules.data_status(last, now, cfg.staleness_seconds, MarketCalendar(cfg.sessions))
    return Freshness(
        symbol,
        primary.provider_name if primary else None,
        status,
        last,
        (now - last).total_seconds() if last else None,
    )


def record_staleness(
    session: Session,
    symbol: str,
    now: datetime | None = None,
    repeat_after: timedelta = timedelta(hours=1),
) -> Freshness:
    """Record a 'stale' data-quality event (at most once per `repeat_after`)."""
    now = now or utcnow()
    f = freshness(session, symbol, now)
    if f.status == "stale":
        inst_id = session.scalar(select(Instrument.id).where(Instrument.symbol == symbol))
        recent = session.scalar(
            select(DataQualityEvent.id)
            .where(
                DataQualityEvent.instrument_id == inst_id,
                DataQualityEvent.event_type == IssueType.STALE.value,
                DataQualityEvent.detected_at > now - repeat_after,
            )
            .limit(1)
        )
        if recent is None:
            _event(
                session,
                QualityIssue(
                    IssueType.STALE,
                    "suspect",
                    f"no fresh verified quote for {f.age_seconds:.0f}s",
                    f.last_observed_at,
                    {
                        "provider": f.provider or "",
                        "age_seconds": Decimal(str(round(f.age_seconds or 0))),
                    },
                ),
                instrument_id=inst_id,
                provider_id=None,
                now=now,
            )
            session.commit()
    return f
