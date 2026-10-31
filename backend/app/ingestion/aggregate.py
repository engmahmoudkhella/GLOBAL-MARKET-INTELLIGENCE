"""Derived 4h and 1d candles built from our own verified 1h bars (owner decision 2026-10-31).

Provider daily bars are never stored: their boundaries are provider-defined (Twelve Data's daily
bar starts 16:00 New York). Our boundaries:
  * 4h: UTC-aligned buckets (00:00, 04:00, ... UTC).
  * 1d: one trading day ends at the instrument's `daily_candle_boundary` (FX/gold 17:00
    America/New_York, crypto 00:00 UTC); the bar spans (previous boundary, boundary] and is
    labelled by its open_time (previous boundary, in UTC). DST is handled by zoneinfo.
A bucket is built only after it has ended. Expected source slots are the 1h slots during which
the session calendar is open; if any expected slot lacks a verified, complete 1h bar the derived
bar is stored as `suspect` (incomplete_source) and excluded from analytics. Nothing is filled.
A suspect derived bar is rebuilt when the missing source bars arrive later; a verified derived
bar is immutable.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.ingestion.service import IngestResult, Target, _event, resolve
from app.models import MarketCandle
from app.quality.rules import IssueType, QualityIssue

SOURCE_TF = "1h"
DERIVED_TAG = "derived:1h"
HOUR = timedelta(hours=1)
DerivedTimeframe = Literal["4h", "1d"]


def buckets(
    t: Target, timeframe: DerivedTimeframe, start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    """Bucket [open, close) intervals overlapping [start, end)."""
    out: list[tuple[datetime, datetime]] = []
    if timeframe == "4h":
        secs = 4 * 3600
        b = datetime.fromtimestamp(int(start.timestamp()) // secs * secs, start.tzinfo)
        while b < end:
            out.append((b, b + timedelta(hours=4)))
            b += timedelta(hours=4)
        return out
    boundary = t.config.daily_candle_boundary
    tz = ZoneInfo(boundary.timezone)
    day: date = start.astimezone(tz).date() - timedelta(days=1)
    last: date = end.astimezone(tz).date() + timedelta(days=1)
    edges = []
    while day <= last:
        edges.append(datetime.combine(day, boundary.time, tz).astimezone(start.tzinfo))
        day += timedelta(days=1)
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b > start and a < end:
            out.append((a, b))
    return out


def build_derived(
    session: Session,
    symbol: str,
    provider_name: str,
    timeframe: DerivedTimeframe,
    start: datetime,
    end: datetime,
    now: datetime | None = None,
) -> IngestResult:
    now = now or utcnow()
    t = resolve(session, symbol, provider_name)
    result = IngestResult(ok=True)
    for b_open, b_close in buckets(t, timeframe, start, end):
        if b_close > now:
            continue  # not finished yet
        expected = []
        slot = b_open
        while slot < b_close:
            if t.calendar.is_open_during(slot, HOUR):
                expected.append(slot)
            slot += HOUR
        if not expected:
            continue  # market closed for the whole bucket
        rows = session.scalars(
            select(MarketCandle)
            .where(
                MarketCandle.instrument_id == t.instrument.id,
                MarketCandle.provider_id == t.provider.id,
                MarketCandle.timeframe == SOURCE_TF,
                MarketCandle.open_time >= b_open,
                MarketCandle.open_time < b_close,
                MarketCandle.data_quality_status == "verified",
                MarketCandle.is_complete.is_(True),
                MarketCandle.derived_from.is_(None),
            )
            .order_by(MarketCandle.open_time)
        ).all()
        if not rows:
            continue  # nothing to build from; the 1h gaps are already reported
        missing = sorted(set(expected) - {r.open_time for r in rows})
        issues = []
        if missing:
            issues.append(
                QualityIssue(
                    IssueType.INCOMPLETE_SOURCE,
                    "suspect",
                    f"{len(missing)} of {len(expected)} expected 1h source bars missing",
                    b_open,
                    {
                        "missing": len(missing),
                        "expected": len(expected),
                        "first_missing": missing[0].isoformat(),
                        "timeframe": timeframe,
                    },
                )
            )
        volumes = [r.volume for r in rows if r.volume is not None]
        values: dict[str, Any] = dict(
            instrument_id=t.instrument.id,
            provider_id=t.provider.id,
            timeframe=timeframe,
            open_time=b_open,
            close_time=b_close,
            open=rows[0].open,
            high=max(r.high for r in rows),
            low=min(r.low for r in rows),
            close=rows[-1].close,
            volume=sum(volumes, Decimal(0)) if len(volumes) == len(rows) else None,
            is_complete=True,
            received_at=now,
            data_quality_status="suspect" if issues else "verified",
            quality_issues=[i.as_json() for i in issues],
            derived_from=DERIVED_TAG,
        )
        base = insert(MarketCandle).values(**values)
        stmt = base.on_conflict_do_update(
            index_elements=["instrument_id", "provider_id", "timeframe", "open_time"],
            set_={
                k: base.excluded[k]
                for k in values
                if k not in ("instrument_id", "provider_id", "timeframe", "open_time")
            },
            where=or_(
                MarketCandle.is_complete.is_(False),
                (MarketCandle.derived_from.is_not(None))
                & (MarketCandle.data_quality_status != "verified"),
            ),
        ).returning(MarketCandle.open_time)
        if session.execute(stmt).first() is not None:
            result.stored += 1
            result.count(values["data_quality_status"])
            for i in issues:
                _event(
                    session, i, instrument_id=t.instrument.id, provider_id=t.provider.id, now=now
                )
            result.issues += len(issues)
        else:
            result.skipped += 1
    session.commit()
    return result
