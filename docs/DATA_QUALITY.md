# GMI – Market Data Quality Rules (SRS §5.3)

Implemented in `backend/app/quality/rules.py` as pure functions, tested in `tests/unit/test_quality_rules.py`,
and applied by `backend/app/ingestion/service.py`. Every stored quote and candle carries a
`data_quality_status` and the list of issues found. Every issue is also written to `data_quality_events`.

| Status | Meaning | Used by analytics/signals? |
|---|---|---|
| `verified` | No issues found | Yes |
| `suspect` | Plausible but unusual (outlier, abnormal spread, duplicate) | No (visible in data-quality views) |
| `rejected` | Impossible or malformed | Never. Hidden from the candles API unless `include_rejected=true`. |

## Rules

| Rule | Severity | Definition |
|---|---|---|
| Invalid OHLC | reject | `high < max(open, close, low)`, `low > min(open, close, high)`, or negative volume |
| Non-positive price | reject | Any price ≤ 0 |
| Crossed quote | reject | `ask < bid` |
| Missing price | reject | Quote with no bid, ask or last price |
| Timestamp skew | reject | Observation more than 5 s in the future of its reception time, or no timezone |
| Misaligned candle | reject | Intraday `open_time` not on a UTC timeframe boundary |
| Duplicate | suspect | Same candle returned twice in one response (flagged as conflicting if values differ) |
| Outlier | suspect | Return vs previous close more than **10 × 1.4826 × MAD** from the median of the last ≤100 returns. Needs at least 21 prior verified prices. **Abstains when MAD = 0** (flat series). |
| Abnormal spread | suspect | Spread above the instrument's `max_spread_bps` if configured. Otherwise more than **10 × the median** of the last ≥20 verified spreads. No fixed spread limit is guessed for any instrument. |
| Missing candles | suspect (event) | Expected intraday bars absent **while the market is open** per the instrument's session calendar. Consecutive gaps are reported once as a window and never re-reported. |
| Stale | suspect (event) | No verified quote newer than `staleness_seconds` while the market is open. At most one event per hour per instrument. |
| Provider outage | suspect (event) | Provider marked `down` after 5 consecutive failures. One event per transition. |

## Storage rules

- **Nothing is filled or estimated.** Gaps stay gaps.
- **Completed candles are immutable.** An incomplete (still-forming) candle may be replaced until it completes.
  A later different value for a completed candle is ignored, and the stored value stays.
- **Official reference rates are not revised silently.** A differing republished value is kept out, and an event is recorded.
- **Freshness** (`/api/v1/markets/{symbol}/quote` → `data_status`): `fresh`, `stale`, `market_closed` or `no_data`.
  `signals_allowed` is true only when the status is `fresh`.

## Known limitations

- Session calendars for USDILS and XAUUSD are provisional and have no holiday data yet, so a holiday can appear as missing candles.
- Outlier and relative-spread rules need history. They are inactive for a new series until enough verified data exists.
- Daily (`1d`) candles are not checked for gaps, because day boundaries are provider-defined.
