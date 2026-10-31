from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from app.instruments.config_schema import SessionCalendar
from app.markets.sessions import MarketCalendar
from app.providers.models import Candle, Quote
from app.quality import rules
from app.quality.rules import IssueType

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)  # Wednesday
FX = MarketCalendar(
    SessionCalendar.model_validate(
        {
            "kind": "weekly",
            "timezone": "America/New_York",
            "weekly_open": {"weekday": "sun", "time": "17:00"},
            "weekly_close": {"weekday": "fri", "time": "17:00"},
        }
    )
)
CRYPTO = MarketCalendar(SessionCalendar.model_validate({"kind": "continuous"}))


def candle(t, o="100", h="101", lo="99", c="100.5", v="1", tf="1m"):
    return Candle(
        "X",
        tf,
        t,
        D(o),
        D(h),
        D(lo),
        D(c),
        None if v is None else D(v),
        t + timedelta(minutes=2),
        True,
    )


def types(issues):
    return [i.type for i in issues]


def test_valid_candle_has_no_issues():
    c = candle(T0)
    assert rules.check_ohlc(c) == [] and rules.check_alignment(c) == []
    assert rules.status_from([]) == "verified"


def test_invalid_ohlc_relationships_rejected():
    assert types(rules.check_ohlc(candle(T0, h="99.5"))) == [IssueType.INVALID_OHLC]  # h < o
    assert types(rules.check_ohlc(candle(T0, lo="100.6"))) == [IssueType.INVALID_OHLC]  # l > c
    assert IssueType.NON_POSITIVE_PRICE in types(rules.check_ohlc(candle(T0, lo="0")))
    assert types(rules.check_ohlc(candle(T0, v="-1"))) == [IssueType.INVALID_OHLC]
    assert rules.status_from(rules.check_ohlc(candle(T0, h="99"))) == "rejected"


def test_misaligned_candle_rejected():
    assert types(rules.check_alignment(candle(T0 + timedelta(seconds=30)))) == [
        IssueType.MISALIGNED_TIMESTAMP
    ]
    assert rules.check_alignment(candle(T0 + timedelta(seconds=30), tf="1d")) == []


def test_duplicates_detected_and_conflicts_flagged():
    issues = rules.find_duplicates([candle(T0), candle(T0), candle(T0, c="100.7")])
    assert len(issues) == 2
    assert issues[0].details["conflicting"] is False
    assert issues[1].details["conflicting"] is True


def test_missing_candles_grouped_into_gaps():
    times = [T0 + timedelta(minutes=i) for i in range(10) if i not in (3, 4, 7)]
    gaps = rules.find_missing_candles(times, "1m", T0, T0 + timedelta(minutes=10), CRYPTO)
    assert [g.details["count"] for g in gaps] == [2, 1]
    assert gaps[0].at == T0 + timedelta(minutes=3)


def test_no_missing_candles_reported_while_market_closed():
    sat = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    assert rules.find_missing_candles([], "1m", sat, sat + timedelta(hours=2), FX) == []
    # ...but the same empty window midweek is one 120-candle gap
    gaps = rules.find_missing_candles([], "1m", T0, T0 + timedelta(hours=2), FX)
    assert len(gaps) == 1 and gaps[0].details["count"] == 120


def test_future_timestamp_rejected():
    q = Quote("X", T0 + timedelta(seconds=30), T0, D("1"), D("1.1"), None)
    assert types(rules.check_quote(q)) == [IssueType.TIMESTAMP_SKEW]


def test_crossed_and_missing_quotes_rejected():
    assert types(rules.check_quote(Quote("X", T0, T0, D("2"), D("1")))) == [IssueType.CROSSED_QUOTE]
    assert types(rules.check_quote(Quote("X", T0, T0))) == [IssueType.MISSING_PRICE]


def test_spread_rules():
    q = Quote("X", T0, T0, D("99"), D("101"))  # 200 bps
    assert rules.spread_bps(q) == D(200)
    assert types(rules.check_quote(q, max_spread_bps=D(50))) == [IssueType.ABNORMAL_SPREAD]
    assert rules.check_quote(q, max_spread_bps=D(500)) == []
    # relative rule: needs history; 200 bps vs median 10 bps -> suspect
    assert types(rules.check_quote(q, recent_spreads=[D(10)] * 20)) == [IssueType.ABNORMAL_SPREAD]
    assert rules.check_quote(q, recent_spreads=[D(10)] * 5) == []  # too little history
    assert rules.check_quote(q, recent_spreads=[D(150)] * 20) == []


def test_outlier_return_uses_median_and_mad():
    # returns cycle through -0.2%..+0.2%: median 0, MAD 0.001 -> threshold 10*1.4826*0.001
    pattern = [D("-0.002"), D("-0.001"), D(0), D("0.001"), D("0.002")]
    closes = [D(100)]
    for i in range(25):
        closes.append(closes[-1] * (1 + pattern[i % 5]))
    assert rules.check_outlier_return(closes, closes[-1] * D("1.014"), T0) == []  # < 1.4826%
    hit = rules.check_outlier_return(closes, closes[-1] * D("1.016"), T0)  # > 1.4826%
    assert types(hit) == [IssueType.OUTLIER] and hit[0].severity == "suspect"
    assert rules.check_outlier_return(closes[:5], closes[-1] * 2, T0) == []  # too short
    assert rules.check_outlier_return([D(100)] * 30, D(150), T0) == []  # MAD 0 -> abstain


def test_data_status():
    sat = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    assert rules.data_status(None, T0, 300, FX) == "no_data"
    assert rules.data_status(T0 - timedelta(seconds=60), T0, 300, FX) == "fresh"
    assert rules.data_status(T0 - timedelta(seconds=301), T0, 300, FX) == "stale"
    assert rules.data_status(sat - timedelta(days=1), sat, 300, FX) == "market_closed"
    assert rules.data_status(sat - timedelta(days=1), sat, 120, CRYPTO) == "stale"
