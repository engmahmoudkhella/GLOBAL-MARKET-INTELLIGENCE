"""Load session calendars with their holiday closures, and the BoI publication calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.instruments.config_schema import InstrumentConfig
from app.markets.sessions import Closure, MarketCalendar
from app.models import MarketHoliday

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def closures(session: Session, calendar: str | None) -> list[Closure]:
    if calendar is None:
        return []
    rows = session.execute(
        select(MarketHoliday.closed_from, MarketHoliday.closed_until).where(
            MarketHoliday.calendar == calendar
        )
    ).all()
    return [(a, b) for a, b in rows]


def market_calendar(session: Session, cfg: InstrumentConfig) -> MarketCalendar:
    return MarketCalendar(cfg.sessions, closures(session, cfg.sessions.holiday_calendar))


def boi_publication_days(session: Session, start: date, end: date) -> list[date]:
    """Days on which a BoI representative rate is expected: Monday-Friday (observed
    2026-10-31: no Saturday/Sunday observations) minus 'boi' holiday closures."""
    closed = {a.astimezone(ISRAEL_TZ).date() for a, _ in closures(session, "boi")}
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in closed:
            out.append(d)
        d += timedelta(days=1)
    return out


def israel_day_start(d: date) -> datetime:
    return datetime.combine(d, time(0), ISRAEL_TZ)
