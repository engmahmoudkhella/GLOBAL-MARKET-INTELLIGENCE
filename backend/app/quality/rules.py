"""Market-data quality rules (SRS §5.3). Pure functions, no I/O.

Each rule returns QualityIssue objects. Severity drives the observation status:
  reject  -> stored as 'rejected' (never used by analytics)
  suspect -> stored as 'suspect'  (excluded from signals; visible in data-quality views)
Missing data is *reported*, never filled.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from statistics import median
from typing import Any, Literal

from app.markets.sessions import MarketCalendar
from app.providers.models import TIMEFRAME_DELTA, Candle, Quote

Severity = Literal["reject", "suspect"]
QualityStatus = Literal["verified", "suspect", "rejected"]

# Defaults, overridable per call. Documented in docs/DATA_QUALITY.md.
FUTURE_TOLERANCE = timedelta(seconds=5)
OUTLIER_MAD_K = Decimal(10)
OUTLIER_MIN_HISTORY = 20
SPREAD_RELATIVE_K = Decimal(10)
SPREAD_MIN_HISTORY = 20
MAD_SCALE = Decimal("1.4826")


class IssueType(StrEnum):
    INVALID_OHLC = "invalid_ohlc"
    NON_POSITIVE_PRICE = "non_positive_price"
    DUPLICATE = "duplicate"
    MISSING_CANDLE = "missing_candle"
    OUTLIER = "outlier"
    STALE = "stale"
    OUTAGE = "outage"
    TIMESTAMP_SKEW = "timestamp_skew"
    MISALIGNED_TIMESTAMP = "misaligned_timestamp"
    ABNORMAL_SPREAD = "abnormal_spread"
    CROSSED_QUOTE = "crossed_quote"
    MISSING_PRICE = "missing_price"
    OUT_OF_SESSION = "out_of_session"
    INCOMPLETE_SOURCE = "incomplete_source"
    REFERENCE_DIVERGENCE = "reference_divergence"


@dataclass(frozen=True)
class QualityIssue:
    type: IssueType
    severity: Severity
    message: str
    at: datetime | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "message": self.message,
            "at": self.at.isoformat() if self.at else None,
            "details": {k: str(v) for k, v in self.details.items()},
        }


def status_from(issues: Iterable[QualityIssue]) -> QualityStatus:
    sev = {i.severity for i in issues}
    if "reject" in sev:
        return "rejected"
    if "suspect" in sev:
        return "suspect"
    return "verified"


# ---------------------------------------------------------------- timestamps
def check_timestamp(
    observed_at: datetime, received_at: datetime, tolerance: timedelta = FUTURE_TOLERANCE
) -> list[QualityIssue]:
    if observed_at.tzinfo is None:
        return [QualityIssue(IssueType.TIMESTAMP_SKEW, "reject", "timestamp has no timezone")]
    if observed_at - received_at > tolerance:
        return [
            QualityIssue(
                IssueType.TIMESTAMP_SKEW,
                "reject",
                "observation is in the future relative to reception",
                observed_at,
                {"skew_seconds": (observed_at - received_at).total_seconds()},
            )
        ]
    return []


def check_alignment(candle: Candle) -> list[QualityIssue]:
    """Intraday candles must start on a UTC timeframe boundary."""
    step = TIMEFRAME_DELTA[candle.timeframe]
    if step >= timedelta(days=1):
        return []  # daily boundaries are provider/session defined
    epoch_s = int(candle.open_time.timestamp())
    if candle.open_time.microsecond or epoch_s % int(step.total_seconds()):
        return [
            QualityIssue(
                IssueType.MISALIGNED_TIMESTAMP,
                "reject",
                f"open_time not aligned to {candle.timeframe}",
                candle.open_time,
            )
        ]
    return []


# ---------------------------------------------------------------- sessions
def check_session(
    observed_at: datetime, calendar: MarketCalendar, provider_flags: dict[str, str] | None = None
) -> list[QualityIssue]:
    """Our session calendar is authoritative; provider 'market open' flags are ignored."""
    if calendar.is_open(observed_at):
        return []
    return [
        QualityIssue(
            IssueType.OUT_OF_SESSION,
            "suspect",
            "observation outside the instrument's trading session",
            observed_at,
            {f"provider_{k}": v for k, v in (provider_flags or {}).items()},
        )
    ]


def check_candle_session(c: Candle, calendar: MarketCalendar) -> list[QualityIssue]:
    step = TIMEFRAME_DELTA[c.timeframe]
    if step >= timedelta(days=1) or calendar.is_open_during(c.open_time, step):
        return []
    return [
        QualityIssue(
            IssueType.OUT_OF_SESSION,
            "suspect",
            "candle lies entirely outside the instrument's trading session",
            c.open_time,
        )
    ]


# ---------------------------------------------------------------- candles
def check_ohlc(c: Candle) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    prices = {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
    bad = [k for k, v in prices.items() if v <= 0]
    if bad:
        issues.append(
            QualityIssue(
                IssueType.NON_POSITIVE_PRICE, "reject", f"non-positive {','.join(bad)}", c.open_time
            )
        )
    if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
        issues.append(
            QualityIssue(
                IssueType.INVALID_OHLC,
                "reject",
                "high/low inconsistent with open/close",
                c.open_time,
                {"o": c.open, "h": c.high, "l": c.low, "c": c.close},
            )
        )
    if c.volume is not None and c.volume < 0:
        issues.append(
            QualityIssue(IssueType.INVALID_OHLC, "reject", "negative volume", c.open_time)
        )
    return issues


def find_duplicates(candles: Sequence[Candle]) -> list[QualityIssue]:
    seen: dict[tuple[str, datetime], Candle] = {}
    issues = []
    for c in candles:
        key = (c.timeframe, c.open_time)
        if key in seen:
            prev = seen[key]
            same = (prev.open, prev.high, prev.low, prev.close) == (c.open, c.high, c.low, c.close)
            issues.append(
                QualityIssue(
                    IssueType.DUPLICATE,
                    "suspect",
                    "duplicate candle" + ("" if same else " with conflicting values"),
                    c.open_time,
                    {"conflicting": not same},
                )
            )
        else:
            seen[key] = c
    return issues


def find_missing_candles(
    open_times: Iterable[datetime],
    timeframe: str,
    start: datetime,
    end: datetime,
    calendar: MarketCalendar,
) -> list[QualityIssue]:
    """Expected intraday bars in [start, end) when the market is open that are absent.

    Only for intraday timeframes. Consecutive missing bars are reported as one gap.
    """
    step = TIMEFRAME_DELTA[timeframe]
    if step >= timedelta(days=1):
        return []
    present = set(open_times)
    secs = int(step.total_seconds())
    t = datetime.fromtimestamp(-(-int(start.timestamp()) // secs) * secs, start.tzinfo)
    gaps: list[QualityIssue] = []
    gap_start: datetime | None = None
    count = 0
    while t < end:
        missing = t not in present and calendar.is_open_during(t, step)
        if missing:
            if gap_start is None:
                gap_start = t
            count += 1
        elif gap_start is not None:
            gaps.append(_gap(gap_start, t, count, timeframe))
            gap_start, count = None, 0
        t += step
    if gap_start is not None:
        gaps.append(_gap(gap_start, t, count, timeframe))
    return gaps


def _gap(start: datetime, end: datetime, count: int, tf: str) -> QualityIssue:
    return QualityIssue(
        IssueType.MISSING_CANDLE,
        "suspect",
        f"{count} missing {tf} candle(s)",
        start,
        {"window_start": start.isoformat(), "window_end": end.isoformat(), "count": count},
    )


def _mad_outlier(value: Decimal, history: Sequence[Decimal], k: Decimal) -> bool:
    med = Decimal(median(history))
    mad = Decimal(median([abs(h - med) for h in history]))
    if mad == 0:
        # No dispersion in the window (e.g. a flat series): the robust scale is undefined, so
        # this rule abstains rather than flag every tick. Documented limitation.
        return False
    return abs(value - med) > k * MAD_SCALE * mad


def check_outlier_return(
    prev_closes: Sequence[Decimal],
    price: Decimal,
    at: datetime | None,
    k: Decimal = OUTLIER_MAD_K,
    min_history: int = OUTLIER_MIN_HISTORY,
) -> list[QualityIssue]:
    """Flag a price whose simple return vs the last close is extreme relative to the
    robust (median/MAD) distribution of recent returns. Needs min_history+1 prior prices."""
    if len(prev_closes) < min_history + 1:
        return []
    rets = [(b - a) / a for a, b in zip(prev_closes[:-1], prev_closes[1:], strict=True)]
    r = (price - prev_closes[-1]) / prev_closes[-1]
    if _mad_outlier(r, rets[-min_history * 5 :], k):
        return [
            QualityIssue(
                IssueType.OUTLIER,
                "suspect",
                "price jump is a statistical outlier",
                at,
                {"return": r.quantize(Decimal("0.000001"))},
            )
        ]
    return []


# ---------------------------------------------------------------- quotes
def check_quote(
    q: Quote,
    recent_spreads: Sequence[Decimal] = (),
    max_spread_bps: Decimal | None = None,
    spread_k: Decimal = SPREAD_RELATIVE_K,
    min_history: int = SPREAD_MIN_HISTORY,
) -> list[QualityIssue]:
    issues = check_timestamp(q.observed_at, q.received_at)
    if q.bid is None and q.ask is None and q.last_price is None:
        return [
            *issues,
            QualityIssue(IssueType.MISSING_PRICE, "reject", "quote has no price", q.observed_at),
        ]
    for name, v in (("bid", q.bid), ("ask", q.ask), ("last", q.last_price)):
        if v is not None and v <= 0:
            issues.append(
                QualityIssue(
                    IssueType.NON_POSITIVE_PRICE, "reject", f"non-positive {name}", q.observed_at
                )
            )
    if q.bid is not None and q.ask is not None and q.bid > 0 and q.ask > 0:
        if q.ask < q.bid:
            issues.append(
                QualityIssue(
                    IssueType.CROSSED_QUOTE,
                    "reject",
                    "ask below bid",
                    q.observed_at,
                    {"bid": q.bid, "ask": q.ask},
                )
            )
        else:
            mid = (q.bid + q.ask) / 2
            spread_bps = (q.ask - q.bid) / mid * 10000
            if max_spread_bps is not None and spread_bps > max_spread_bps:
                issues.append(
                    QualityIssue(
                        IssueType.ABNORMAL_SPREAD,
                        "suspect",
                        "spread above configured maximum",
                        q.observed_at,
                        {"spread_bps": spread_bps.quantize(Decimal("0.01"))},
                    )
                )
            elif len(recent_spreads) >= min_history:
                med = Decimal(median(recent_spreads))
                if med > 0 and spread_bps > spread_k * med:
                    issues.append(
                        QualityIssue(
                            IssueType.ABNORMAL_SPREAD,
                            "suspect",
                            "spread far above recent median",
                            q.observed_at,
                            {
                                "spread_bps": spread_bps.quantize(Decimal("0.01")),
                                "median_bps": med.quantize(Decimal("0.01")),
                            },
                        )
                    )
    return issues


def spread_bps(q: Quote) -> Decimal | None:
    if q.bid is None or q.ask is None or q.bid <= 0 or q.ask < q.bid:
        return None
    return (q.ask - q.bid) / ((q.bid + q.ask) / 2) * 10000


# ---------------------------------------------------------------- freshness
DataStatus = Literal["fresh", "stale", "market_closed", "no_data"]


def data_status(
    last_observed_at: datetime | None,
    now: datetime,
    staleness_seconds: int,
    calendar: MarketCalendar,
) -> DataStatus:
    """Freshness of an instrument's latest verified observation.

    While the market is closed an old quote is expected, so the status is 'market_closed'
    (signals stay disabled either way; only 'fresh' enables them)."""
    if last_observed_at is None:
        return "no_data"
    if not calendar.is_open(now):
        return "market_closed"
    if (now - last_observed_at).total_seconds() > staleness_seconds:
        return "stale"
    return "fresh"
