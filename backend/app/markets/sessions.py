"""Market session calendars: is the market open at a given instant?

Evaluated in the calendar's own timezone so DST transitions (e.g. New York) are handled by
zoneinfo. Holiday data does not exist yet (calendars are flagged `provisional`); until it does,
holiday closures are not known and gap detection may report them as missing data.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.instruments.config_schema import SessionCalendar

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_WEEK = 7 * 24 * 3600


def _seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


class MarketCalendar:
    def __init__(self, cfg: SessionCalendar) -> None:
        self.cfg = cfg
        self.tz = ZoneInfo(cfg.timezone)

    @property
    def is_continuous(self) -> bool:
        return self.cfg.kind == "continuous"

    def is_open(self, ts: datetime) -> bool:
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.cfg.kind == "continuous":
            return True
        assert self.cfg.weekly_open is not None and self.cfg.weekly_close is not None
        local = ts.astimezone(self.tz)
        tod = local.hour * 3600 + local.minute * 60 + local.second
        pos = local.weekday() * 86400 + tod
        open_pos = _WEEKDAYS[self.cfg.weekly_open.weekday] * 86400 + _seconds(
            self.cfg.weekly_open.time
        )
        close_pos = _WEEKDAYS[self.cfg.weekly_close.weekday] * 86400 + _seconds(
            self.cfg.weekly_close.time
        )
        if open_pos < close_pos:
            in_week = open_pos <= pos < close_pos
        else:  # wraps over the week boundary (e.g. Sun 17:00 -> Fri 17:00)
            in_week = pos >= open_pos or pos < close_pos
        if not in_week:
            return False
        for br in self.cfg.daily_breaks:
            start, end = _seconds(br.start), _seconds(br.end)
            if start <= tod < end:
                return False
        return True

    def is_open_during(self, start: datetime, length: timedelta) -> bool:
        """True if the market is open at any minute boundary in [start, start + length)."""
        if self.is_continuous:
            return True
        step = timedelta(minutes=1) if length <= timedelta(hours=4) else timedelta(minutes=15)
        t = start
        end = start + length
        while t < end:
            if self.is_open(t):
                return True
            t += step
        return False
