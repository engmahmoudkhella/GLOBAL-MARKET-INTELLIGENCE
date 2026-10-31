"""Load session calendars with their closures, and the BoI publication calendar.

Closures come from two tables:
  * market_holidays (kind='closure'): algorithmic / conventional holidays, flagged assumptions;
  * special_closures: manual one-off closures with a source URL (e.g. election days).
market_holidays rows with kind='reduced_liquidity' are NOT closures; they only annotate gaps.
A BoI-published non-publication calendar, once fetchable, is authoritative over computed dates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.instruments.config_schema import InstrumentConfig
from app.markets.sessions import Closure, MarketCalendar
from app.models import MarketHoliday, SpecialClosure

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
NEW_YORK_TZ = ZoneInfo("America/New_York")


def special_closure_window(calendar: str, d: date) -> Closure:
    """BoI: the Israeli calendar day. FX/XAU: the session day ending 17:00 New York on `d`."""
    if calendar == "boi":
        start = datetime.combine(d, time(0), ISRAEL_TZ)
        return start, start + timedelta(days=1)
    end = datetime.combine(d, time(17), NEW_YORK_TZ)
    return datetime.combine(d - timedelta(days=1), time(17), NEW_YORK_TZ), end


@dataclass(frozen=True)
class NamedWindow:
    start: datetime
    end: datetime
    name: str
    source: str


def closure_windows(session: Session, calendar: str | None) -> list[NamedWindow]:
    if calendar is None:
        return []
    out = [
        NamedWindow(h.closed_from, h.closed_until, h.name, h.source)
        for h in session.scalars(
            select(MarketHoliday).where(
                MarketHoliday.calendar == calendar, MarketHoliday.kind == "closure"
            )
        )
    ]
    for s in session.scalars(select(SpecialClosure).where(SpecialClosure.calendar == calendar)):
        a, b = special_closure_window(calendar, s.closure_date)
        out.append(NamedWindow(a, b, s.reason, s.source_url))
    return out


def closures(session: Session, calendar: str | None) -> list[Closure]:
    return [(w.start, w.end) for w in closure_windows(session, calendar)]


def reduced_liquidity_windows(session: Session, calendar: str | None) -> list[NamedWindow]:
    if calendar is None:
        return []
    return [
        NamedWindow(h.closed_from, h.closed_until, h.name, h.source)
        for h in session.scalars(
            select(MarketHoliday).where(
                MarketHoliday.calendar == calendar, MarketHoliday.kind == "reduced_liquidity"
            )
        )
    ]


def market_calendar(session: Session, cfg: InstrumentConfig) -> MarketCalendar:
    return MarketCalendar(cfg.sessions, closures(session, cfg.sessions.holiday_calendar))


def boi_closed_days(session: Session) -> dict[date, str]:
    """Israeli dates on which BoI is not expected to publish, with the reason."""
    return {w.start.astimezone(ISRAEL_TZ).date(): w.name for w in closure_windows(session, "boi")}


def boi_publication_days(session: Session, start: date, end: date) -> list[date]:
    """Days on which a BoI representative rate is expected: Monday-Friday (observed
    2026-10-31) minus 'boi' holiday closures and special closures."""
    closed = boi_closed_days(session)
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in closed:
            out.append(d)
        d += timedelta(days=1)
    return out


def israel_day_start(d: date) -> datetime:
    return datetime.combine(d, time(0), ISRAEL_TZ)
