"""Twelve Data credit budget for the ingestion schedule (owner decision 2026-10-31).

The schedule must fit the configured plan, or configuration validation fails at startup.
Assumes the market is always open (worst case); tasks additionally skip provider calls while
the session calendar is closed, which only lowers real usage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

TWELVEDATA_SYMBOLS = ("USDILS", "XAUUSD")
CANDLES_1H_INTERVAL_SECONDS = 3600
CREDITS_PER_CALL = 1  # /quote and /time_series cost 1 credit per symbol


@dataclass(frozen=True)
class TwelveDataSchedule:
    quote_interval_seconds: int
    candles_1m_interval_seconds: int
    candles_1h_interval_seconds: int = CANDLES_1H_INTERVAL_SECONDS
    symbols: int = len(TWELVEDATA_SYMBOLS)

    def intervals(self) -> tuple[int, ...]:
        return (
            self.quote_interval_seconds,
            self.candles_1m_interval_seconds,
            self.candles_1h_interval_seconds,
        )

    def peak_credits_per_minute(self) -> int:
        """Worst case: every task's calls that can land in the same minute coincide."""
        return self.symbols * CREDITS_PER_CALL * sum(math.ceil(60 / i) for i in self.intervals())

    def credits_per_day(self) -> int:
        return self.symbols * CREDITS_PER_CALL * sum(math.ceil(86400 / i) for i in self.intervals())


@dataclass(frozen=True)
class BudgetCheck:
    ok: bool
    peak_per_minute: int
    per_day: int
    limit_per_minute: Decimal
    limit_per_day: Decimal | None
    message: str


def check_budget(
    schedule: TwelveDataSchedule, credits_per_minute: int, credits_per_day: int, headroom: Decimal
) -> BudgetCheck:
    lim_min = Decimal(credits_per_minute) * headroom
    lim_day = Decimal(credits_per_day) * headroom if credits_per_day > 0 else None
    peak, day = schedule.peak_credits_per_minute(), schedule.credits_per_day()
    problems = []
    if peak > lim_min:
        problems.append(
            f"peak {peak} credits/min > {lim_min} allowed "
            f"({credits_per_minute}/min x headroom {headroom})"
        )
    if lim_day is not None and day > lim_day:
        problems.append(
            f"{day} credits/day > {lim_day} allowed ({credits_per_day}/day x headroom {headroom})"
        )
    msg = (
        (
            "Twelve Data schedule does not fit the configured plan: "
            + "; ".join(problems)
            + ". Increase the polling intervals or configure the paid plan's limits."
        )
        if problems
        else f"fits: peak {peak}/min, {day}/day"
    )
    return BudgetCheck(not problems, peak, day, lim_min, lim_day, msg)
