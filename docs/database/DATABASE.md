# GMI – Database Design (proposal, v0)

**Status:** Phase 1 tables are **implemented** (migration `0001_foundation`): `users`, `user_sessions`, `instruments`,
`market_providers`, `instrument_provider_symbols`, `system_audit_logs`, `job_runs`. Migration `0003_market_data` adds `market_quotes` and `market_candles` (hypertables, with compression and retention policies per D7), `data_quality_events` and `official_reference_rates`. Migration `0004_derived_candles` adds `market_candles.derived_from` and sets each instrument's `daily_candle_boundary`. Other tables are a proposal and arrive in their phase.

Engine: PostgreSQL 16 + TimescaleDB. All timestamps are `timestamptz` and stored in UTC.
Prices use `NUMERIC(24,10)`. Money (balances, fees, P&L) uses `NUMERIC(28,8)`.
Probabilities use `NUMERIC(7,4)` in the range 0–100 and are enforced to sum to 100 by a CHECK constraint (tolerance 0.01).

## Conventions

- Surrogate `id BIGINT GENERATED ALWAYS AS IDENTITY` everywhere except hypertables, which use composite natural keys.
- `created_at` and `updated_at` default to `now()`.
- Enumerations are Postgres `TEXT` columns with `CHECK` constraints, which are easier to migrate than native enums.
- Every foreign key is indexed.

## Entity overview

```
users ─┬─ user_sessions
       ├─ paper_accounts ─┬─ paper_orders ── paper_fills
       │                  ├─ paper_positions
       │                  └─ paper_transactions (double-entry ledger)
       ├─ alerts ── notification_deliveries
       └─ importer_scenarios

instruments ─┬─ instrument_provider_symbols ── market_providers
             ├─ market_quotes (hypertable)
             ├─ market_candles (hypertable)
             ├─ technical_indicators (hypertable)
             ├─ technical_patterns
             ├─ data_quality_events
             ├─ news_asset_impacts ── news_articles
             ├─ forecasts ─┬─ forecast_inputs
             │             ├─ forecast_evaluations
             │             └─ trading_signals
             └─ model_registry

economic_series ── economic_observations
economic_events
system_audit_logs, job_runs
```

## Tables from SRS §6.1 (kept), with refinements

| Table | Refinements |
|---|---|
| `users` | `role` ∈ {admin, analyst, viewer}. `email` unique, stored lowercase (CHECK). `timezone` IANA name. `preferred_language` ∈ {ar, en}. `is_active`. |
| `instruments` | `symbol` unique. Primary instruments are USDILS, XAUUSD and BTCUSD. **BTCUSDT** is a separate `role='secondary'` instrument (quote USDT) so Binance data is never stored as BTCUSD. Adds `role` ∈ {primary, secondary}. `configuration_json` is validated by the `InstrumentConfig` Pydantic schema. |
| `market_providers` | Adds `capabilities` (jsonb list), `licence_notes`, `consecutive_failures`. **Credentials are never stored here.** They come from env or the secret store. |
| `market_quotes` | Hypertable on `observed_at`. PK `(instrument_id, provider_id, observed_at)`. Adds `latency_ms`. `data_quality_status` ∈ {verified, suspect, rejected}. |
| `market_candles` | Hypertable on `open_time`. PK `(instrument_id, provider_id, timeframe, open_time)`. Adds `is_complete`, `data_quality_status`, `received_at`. |
| `technical_indicators` | Hypertable on `timestamp`. Unique `(instrument_id, timeframe, timestamp, indicator_name, params_hash)`. |
| `news_articles` | Stores **title, summary and URL only**, never full copyrighted text. Unique `(provider_id, external_id)`. Adds `claim_type`. |
| `news_asset_impacts` | `sentiment` and `expected_direction` are separate columns (sentiment ≠ direction, SRS §9.3). Adds `time_sensitivity`, `confirmation_status`. |
| `economic_events` | Adds `released_at` (when the actual value became public) and `unit`. |
| `forecasts` | `status` ∈ {pending, evaluated, not_evaluable, invalidated} (plan §0.4). Adds `reference_provider_id`, `neutral_band`, `horizon_basis` ∈ {trading_time, calendar_time} (`expires_at` is the calendar timestamp of the trading-time expiry). Adds `horizon`, `is_experimental`, `data_status_at_issue`. A **trigger blocks UPDATE of every column except `status`** and blocks DELETE. |
| `forecast_evaluations` | Insert-only. Adds `outcome` ∈ {evaluated, not_evaluable}, `not_evaluable_reason`, `actual_quote_observed_at`, `actual_provider_id`, `price_type` ∈ {mid, last}, `brier_score`, `boi_reference_rate` and `boi_reference_date` (USD/ILS display only, not scored). `actual_price` is NULL when not evaluable. |
| `trading_signals` | Insert-only except `status`. FK to `forecasts`. |
| `paper_accounts` | Adds `account_type` ∈ {forex, gold, bitcoin, combined}. `current_balance` is a cached value, reconciled against the ledger. |
| `paper_orders` | Adds `limit_price`, `stop_price`, `time_in_force`, `parent_position_id` (for SL/TP), `reject_reason`. A `simulated` column is always true and protected by a CHECK constraint. |
| `paper_positions` | Adds `fees_total`, `mfe`, `mae`. |
| `paper_transactions` | Double-entry: `debit_account`, `credit_account`, `amount`, `currency`. An invariant test asserts the ledger balances. |
| `alerts` | `condition_json` validated per `alert_type`. Adds `channels`, `cooldown_seconds`. |
| `model_registry` | Adds `artifact_uri`, `artifact_sha256`, `feature_set_hash`, `baseline_comparison` (jsonb). `deployment_status` ∈ {candidate, approved, retired}. |
| `system_audit_logs` | Insert-only (trigger `trg_audit_log_append_only`; the only allowed UPDATE is the FK's `ON DELETE SET NULL` of `user_id`). |

## Added tables

| Table | Key columns |
|---|---|
| `user_sessions` | token_hash (SHA-256 of a 256-bit token), csrf_token_hash, user_id, created_at, expires_at, revoked_at, ip, user_agent |
| `instrument_provider_symbols` | instrument_id, provider_id, provider_symbol, notes (e.g. "BTCUSDT – USDT quote, not USD") |
| `official_reference_rates` | instrument_id, provider_id, rate_date, rate, published_at, received_at. Unique (instrument, provider, rate_date). Reference only, never a quote. **Implemented (0003).** |
| `data_quality_events` | **Implemented (0003).** instrument_id, provider_id, event_type ∈ {missing_candle, duplicate, invalid_ohlc, outlier, stale, outage, timestamp_skew, abnormal_spread}, detected_at, window_start, window_end, details_json |
| `economic_series` | code, country, name, unit, frequency, source, source_url |
| `economic_observations` | series_id, period_date, value, released_at, vintage. Unique (series_id, period_date, vintage). |
| `technical_patterns` | instrument_id, timeframe, pattern_type, detected_at, boundaries_json, confirmation_status, invalidation_condition |
| `forecast_inputs` | forecast_id, candle_range_start, candle_range_end, feature_set_hash, input_snapshot_uri |
| `paper_fills` | order_id, quantity, price, spread_cost, slippage, commission, filled_at, price_basis ∈ {bid_ask, estimated_spread} |
| `importer_rate_entries` | user_id, rate (executable USD/ILS buy rate entered by the user), source_note, entered_at, boi_rate, boi_rate_date (reference at entry time, nullable) |
| `importer_scenarios` | user_id, rate_entry_id, inputs_json, results_json, created_at |
| `notification_deliveries` | alert_id, channel, status, attempts, last_error, sent_at |
| `job_runs` | job_name, idempotency_key (unique), status, started_at, finished_at, error |

## Retention (decision D7)

- `market_candles` 1m: **raw (uncompressed) for 2 years, then compressed**. Not dropped automatically.
- `market_candles` 1h and above: **kept forever**.
- `market_quotes`: compress after 7 days, drop after 90 days (quotes are not covered by D7 and can be revisited).
- Continuous aggregates are built from 1m candles where the provider does not supply higher timeframes.
- Forecasts, evaluations, signals, ledger and audit logs: **never deleted**.
