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
| **Out of session** | suspect | Quote observed, or intraday candle lying entirely, outside the instrument's session calendar. **Provider "market open" flags are ignored.** The provider flag is kept in the event details for audit. Excluded from indicators, candles, forecasts and evaluation. The UI shows it separately as "excluded – market closed / weekend". |
| Incomplete source | suspect | A derived 4h/1d bar is missing ≥1 expected verified 1h source bar. It is rebuilt automatically when the missing bars arrive. |
| Reference divergence | suspect (event) | Twelve Data USD/ILS near BoI publication differs from the BoI representative rate by more than the threshold (default 0.5 %) |
| Stale | suspect (event) | No verified quote newer than `staleness_seconds` while the market is open. At most one event per hour per instrument. |
| Provider outage | suspect (event) | Provider marked `down` after 5 consecutive failures. One event per transition. |

## Derived candles

Only 1m/5m/15m/1h bars are taken from providers. **4h and 1d bars are always derived locally** from verified, complete
1h bars (`derived_from = 'derived:1h'`):
- 4h: UTC-aligned buckets (00, 04, 08, 12, 16, 20 UTC).
- 1d: the trading day ends at the instrument's `daily_candle_boundary`: **17:00 America/New_York** for USD/ILS and XAU/USD
  (FX day roll, DST-aware), **00:00 UTC** for BTC. A bar opens at the previous boundary.
- Expected source hours are those in which the session calendar is open, so gold's 17:00–18:00 NY break is not expected.
- Built only after the bucket ends. Verified derived bars are immutable.

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
