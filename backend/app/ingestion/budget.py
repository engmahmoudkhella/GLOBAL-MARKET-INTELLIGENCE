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


def check_against_plan(
    schedule: TwelveDataSchedule,
    configured_per_minute: int,
    configured_per_day: int,
    headroom: Decimal,
    plan_per_minute: int,
    plan_per_day: int,
    plan_category: str,
) -> BudgetCheck:
    """Compare configuration with the plan reported by /api_usage, then re-check the schedule
    against the *actual* plan limits. plan_per_day/configured_per_day: 0 = no daily cap."""
    problems = []
    if configured_per_minute > plan_per_minute:
        problems.append(
            f"configured {configured_per_minute} credits/min exceeds the "
            f"{plan_category} plan's {plan_per_minute}/min"
        )
    if plan_per_day > 0 and (configured_per_day == 0 or configured_per_day > plan_per_day):
        problems.append(
            f"configured daily limit "
            f"{configured_per_day or 'unlimited'} exceeds the {plan_category} "
            f"plan's {plan_per_day}/day"
        )
    actual = check_budget(schedule, plan_per_minute, plan_per_day, headroom)
    if not actual.ok:
        problems.append(actual.message)
    msg = (
        ("Twelve Data plan check failed: " + "; ".join(problems))
        if problems
        else f"plan {plan_category} ok: {actual.message}"
    )
    return BudgetCheck(
        not problems,
        actual.peak_per_minute,
        actual.per_day,
        actual.limit_per_minute,
        actual.limit_per_day,
        msg,
    )


def check_coingecko_budget(
    interval_seconds: int, per_minute: int, per_month: int, headroom: Decimal
) -> str | None:
    """Returns an error message if polling every `interval_seconds` exceeds the Demo plan
    (worst case: 31-day month). None when it fits."""
    calls_min = math.ceil(60 / interval_seconds)
    calls_month = math.ceil(31 * 86400 / interval_seconds)
    problems = []
    if calls_min > per_minute * headroom:
        problems.append(f"{calls_min} calls/min > {per_minute * headroom}")
    if calls_month > per_month * headroom:
        problems.append(f"{calls_month} calls/month > {per_month * headroom}")
    if problems:
        return (
            "CoinGecko schedule does not fit the configured plan: "
            + "; ".join(problems)
            + ". Increase GMI_COINGECKO_QUOTE_INTERVAL_SECONDS."
        )
    return None
