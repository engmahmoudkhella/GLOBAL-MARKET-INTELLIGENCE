"""Holiday calendars.

Closures are stored in `market_holidays` (calendar key, closed_from/closed_until instants) and
applied by MarketCalendar. Every seeded entry carries `is_assumption=true` and a source note until
it is confirmed by observed provider/publication behaviour (gap events reveal disagreements).

Israeli rest days (Bank of Israel publication calendar) are computed with pyluach. ASSUMPTION:
BoI does not publish on these full rest days: Rosh Hashana (2 days), Yom Kippur, Sukkot day 1,
Shemini Atzeret, Pesach day 1, Pesach day 7, Shavuot, Yom HaAtzmaut.
"""

from __future__ import annotations

from datetime import date, timedelta

from pyluach import dates, hebrewcal

BOI_REST_DAY_NAMES = frozenset(
    {
        "1 Rosh Hashana",
        "2 Rosh Hashana",
        "Yom Kippur",
        "1 Succos",
        "Shmini Atzeres",
        "1 Pesach",
        "7 Pesach",
        "Shavuos",
    }
)


def yom_haatzmaut(gregorian_year: int) -> date:
    """Israel Independence Day (5 Iyar, with the statutory postponement rules:
    Friday or Saturday -> preceding Thursday; Monday -> Tuesday)."""
    for heb_year in (gregorian_year + 3760, gregorian_year + 3761):
        g: date = dates.HebrewDate(heb_year, 2, 5).to_pydate()  # month 2 = Iyar
        if g.year == gregorian_year:
            wd = g.weekday()  # Mon=0 ... Sun=6
            if wd == 4:
                return g - timedelta(days=1)
            if wd == 5:
                return g - timedelta(days=2)
            if wd == 0:
                return g + timedelta(days=1)
            return g
    raise ValueError(gregorian_year)


def israeli_rest_days(year: int) -> list[tuple[date, str]]:
    out = []
    d = date(year, 1, 1)
    while d.year == year:
        name = (
            dates.GregorianDate(d.year, d.month, d.day)
            .to_heb()
            .holiday(israel=True, prefix_day=True)
        )
        if name in BOI_REST_DAY_NAMES:
            out.append((d, name))
        d += timedelta(days=1)
    out.append((yom_haatzmaut(year), "Yom HaAtzmaut"))
    return sorted(out)


_ = hebrewcal  # imported for pyluach's calendar data
