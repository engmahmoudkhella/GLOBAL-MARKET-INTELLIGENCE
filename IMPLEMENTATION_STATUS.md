# Implementation Status

Last updated: 2026-10-31 (Phase 2 groundwork). Phase numbering follows the approved plan (`docs/architecture/IMPLEMENTATION_PLAN.md` §0, §6).

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository inspection and technical plan | **Done. Approved 2026-10-31** with decisions D1–D9. |
| 1 | Foundation: repo layout, DB + migrations, auth/RBAC, instruments, Docker, CI, AR/EN shell | **Accepted.** GitHub CI green (run #2, 2026-10-31). |
| 2 | Market data (Twelve Data, Coinbase, BoI, CoinGecko, Binance secondary) | **In progress, code-complete for v1 sources.** All five adapters exist. BoI, Twelve Data and Coinbase ticker/candles are verified against owner recordings. CoinGecko and Binance are doc-based. Remaining for acceptance: live run on the VPS (reachability, contract check with byte-exact recordings, Grow key, first real ingestion). |
| 3 | Importer Advisor (moved up) | Not started |
| 4 | Technical, fundamental and news analysis | Not started |
| 5 | Forecasting, including the **Forecast Track Record** page (plan §0.4) | Not started |
| 6 | AI Chief Analyst and cross-asset analysis | Not started |
| 7 | Paper trading | Not started |
| 8 | Dashboard, notifications, reports | Not started |
| 9 | Hardening and acceptance | Not started |

## Phase 1 – acceptance evidence

| Criterion (plan §6 gate) | Evidence |
|---|---|
| `docker compose up` gives a healthy stack | Verified 2026-10-31. db, redis, migrate (exit 0), api (healthy), worker, beat, web and nginx all came up. `/health/ready` → `{"ok":true}` through nginx. The heartbeat job was recorded in `job_runs` by worker and beat. |
| DB with migrations | `0001_foundation` and `0002_seed_reference_data`. Tests cover upgrade, downgrade→upgrade and **no drift between models and migrations**. |
| Auth with RBAC tests | 13 auth API tests and 4 RBAC/admin tests (login, logout, CSRF, expiry, revocation, rate limit, generic errors, no signup endpoint) |
| Instrument seed | USDILS, XAUUSD, BTCUSD (primary) and BTCUSDT (secondary). Configs are schema-validated. No prices. BTCUSD maps only to USD sources. |
| CI green | **Green on GitHub** (run #2). Run #1 hung in the e2e job: `wait-on` probes with HEAD, which FastAPI answers with 405. Fixed with `http-get://`, bounded waits and job timeouts. |
| AR/EN shell | Playwright: 18/18 passed (desktop + mobile). RTL/LTR, locale switch, 21 sections including Forecast Track Record, paper-only banner, logout. Run against both `next start` and the Compose stack behind nginx. |

### Test results (local, 2026-10-31)

- Backend: `pytest` **51 passed** (19 unit, 32 integration on real PostgreSQL 16 + TimescaleDB 2.31.0). `ruff check`, `ruff format --check` and `mypy --strict` are clean.
- Frontend: `eslint` clean, `tsc --noEmit` clean, `next build` OK, Playwright **18 passed**.
- Guard: `scripts/check_no_real_trading.py` finds no forbidden patterns.

### Known limitations and notes

- **HTTPS is not configured yet.** Compose serves HTTP on port 8080. Until the TLS override exists (Phase 9), use an SSH tunnel to reach the VPS.
- Session calendars for USDILS and XAUUSD are **provisional** placeholders (`provisional: true`). Provider sessions and holidays replace them in Phase 2.
- The BoI series identifier in the provider mapping (`USD`) is a placeholder, to be confirmed in Phase 2.
- The rate limiter fails open if Redis is down (deliberate, documented in SECURITY.md).
- Docker images were verified in the build sandbox using a local proxy wrapper. On a normal host, `docker compose up --build` needs internet access to PyPI and npm.
- TypeScript is pinned to 6.x because `typescript-eslint` does not support TypeScript 7 yet.

## Phase 2 – groundwork (2026-10-31)

| Item | Status | Evidence |
|---|---|---|
| Provider interface (SRS §5.1) with capability flags | Done | `app/providers/base.py`. Unsupported calls raise `CapabilityNotSupported`. |
| HTTP client: timeouts, retry + exponential backoff with jitter, Retry-After, pacing | Done | 6 unit tests |
| Session calendars (DST-aware, daily breaks) | Done | 5 unit tests (EST/EDT boundaries, gold break, crypto 24/7) |
| Data-quality rules (all SRS §5.3 checks) | Done | 11 unit tests with hand-checked thresholds. See `docs/DATA_QUALITY.md`. |
| Coinbase Exchange adapter (BTC-USD primary) | Done, **live contract unverified** | 15 unit tests on doc-derived fixtures |
| Bank of Israel adapter (reference rates) | Done, **live contract unverified** | 11 unit tests on doc-derived fixtures |
| Storage: quotes/candles hypertables, DQ events, reference rates (migration 0003) | Done | Migration up/down, no model drift, compression/retention policies verified (candles never auto-deleted) |
| Ingestion service (validation, immutability, gaps, staleness, provider health) | Done | 11 integration tests on TimescaleDB, including outage → degraded → down → recovery without crashing |
| Celery ingestion tasks + backfill CLI | Done, off by default (`GMI_INGESTION_ENABLED`) | Schedule tests (only registered providers; no Twelve Data; BTCUSD only from Coinbase) |
| Market API: quote (freshness, `signals_allowed`), candles, reference rates | Done | 7 integration tests |
| Overview shows data status per instrument; price only when verified | Done | Playwright (AR/EN, desktop/mobile) and exact decimal-string rounding test |
| VPS scripts: `check_provider_reachability.py`, `check_provider_contracts.py` | Written, **not yet run** (no VPS yet) | Fail cleanly in the sandbox (egress blocked) |
| Twelve Data adapter (USDILS, XAUUSD) | Done. `/quote` verified against **recorded** responses. `/time_series` and `/api_usage` are doc-derived. | 17 unit tests, including exact parsing of both recorded responses, header-only API key and error mapping |
| Session calendar authoritative: `suspect: out_of_session` | Done | Recorded Saturday quotes for USDILS and XAUUSD stored as suspect and excluded from freshness. Weekend candle suspect. API `latest_excluded`. Playwright checks the label (e2e seed uses the recorded fixture). |
| Derived 4h/1d candles (provider daily bars never stored) | Done | 8 integration tests: NY 17:00 boundary across DST end, gold break, missing hour → suspect → backfilled → verified, immutability, 4h UTC |
| Twelve Data credit budget + fail-loud config validation | Done | 7 unit tests and schedule tests |
| USD/ILS vs BoI cross-check | Done | 5 integration tests with hand-computed divergences, plus the task retry test |
| CoinGecko reference, Binance secondary, holiday calendars | Done (see below) | — |

**Phase 2 is not complete.** Its acceptance gate ("all three instruments retrieve data") needs live runs on the VPS
(contract checks, reachability, the Grow key) and CoinGecko and Binance.

### Test results (local, 2026-10-31, after Twelve Data findings)

- Backend: **162 passed** (unit + integration on TimescaleDB). ruff and mypy --strict clean.
- Frontend: Playwright **20 passed**, including the excluded weekend-quote label.

### Earlier (Phase 2 groundwork)

- Backend: **118 passed** (unit and integration on PostgreSQL 16 + TimescaleDB 2.31.0). ruff, ruff format and mypy --strict are clean.
- Frontend: eslint and tsc clean, build OK, Playwright **20 passed** (18 e2e + decimal-rounding unit test on 2 projects).

## Owner recordings 2026-10-31 (findings A–I): code and tests

| Finding | Code changed | Tests |
|---|---|---|
| A. BoI publication time | `config.boi_publication_fallback_time` = 12:30 IST (assumption). `boi.parse_latest_json` uses `lastUpdate`. The cross-check window centres on it. | `test_boi_provider::test_recorded_json_usd_exact_decimal_and_publication_time`; `test_recorded_findings::test_crosscheck_uses_lastupdate_when_present`, `::test_fallback_publication_time_is_12_30_israel_in_both_seasons`; `test_twelvedata_rules::test_crosscheck_without_data` |
| B. BoI Mon–Fri, 27 Oct missing | `markets/calendars.boi_publication_days`; `ingestion/service.record_reference_gaps` (`missing_reference` events, never filled) | `test_recorded_findings::test_recorded_boi_series_gap_on_tue_27_oct_only` (exact series), `::test_boi_publication_calendar_weekdays_minus_holidays` |
| C. `edge.boi.org.il` SDMX, raw attributes | `boi.py` hosts and XML parser. Migration 0005 `attributes_json`. Reachability script checks 3 BoI domains. | `test_boi_provider::test_adapter_uses_verified_hosts_and_no_format_param`, `::test_sdmx_xml_series_parsed_with_raw_attributes`; `test_recorded_findings::test_raw_attributes_stored_and_merged` |
| D. JSON numbers, unit, % change | `boi._json_number`, `rate / unit`, `current_change_pct` stored raw | `test_boi_provider::test_rates_divided_by_unit` (JPY, LBP, EUR), `::test_negative_and_zero_change_accepted`, `::test_contract_violations_rejected`, `::test_sdmx_and_json_agree_on_2026_10_30` |
| E. XML browser copy, not byte-exact | Fixture labelled "browser copy" with a reconstructed wrapper. The parser uses defusedxml. | `test_boi_provider::test_bad_sdmx_rejected` (missing space between attributes is rejected), `::test_xml_entity_expansion_refused` |
| F. Coinbase ticker | `coinbase.get_latest_quote` (strict strings), `parsing.to_utc` (9 digits), `parsing.note_unknown_fields` | `test_recorded_findings::test_recorded_ticker_true_mid_and_both_time_precisions`, `::test_unknown_ticker_field_ignored_and_logged_once`, `::test_ticker_required_field_types_strict` |
| G. Coinbase candle order, incomplete hour | `coinbase._parse_candle` (explicit columns, order assertion). `service.ingest_candles` drops incomplete candles (all providers). | `test_recorded_findings::test_recorded_candles_mapped_by_explicit_column_order`, `::test_swapped_columns_detected`, `::test_candle_strings_rejected`; integration `::test_recorded_coinbase_current_hour_dropped` |
| H. Twelve Data series not UTC | `twelvedata._series`: timezone=UTC always, meta timezone optional, future bars reject the response | `test_recorded_findings::test_recorded_non_utc_series_rejected_as_future`, `::test_utc_series_without_meta_timezone_accepted_latest_incomplete`; integration `::test_utc_saturday_bars_stored_out_of_session_latest_dropped`, `::test_recorded_non_utc_series_never_stored` |
| I. Twelve Data plan from `/api_usage` | `twelvedata.parse_plan/get_plan`, `budget.check_against_plan`, `celery_app.verify_twelvedata_plan` on `beat_init` | `test_recorded_findings::test_recorded_api_usage_parsed`, `::test_plan_check_*` (3), `::test_beat_startup_plan_verification`; `test_twelvedata_provider::test_api_usage_status` |

## Phase 2 – continued (2026-10-31)

| Item | Status | Tests |
|---|---|---|
| CoinGecko reference (BTC/USD) | Implemented, doc-based. Monthly budget validation. Coinbase cross-check. UI attribution. | `test_coingecko_binance` (unit 5, integration 4), schedule/budget tests, Playwright attribution check |
| Binance BTCUSDT secondary | Implemented, doc-based (`data-api.binance.vision`). 451 = rejected. Only `BTCUSDT`. Derived 4h/1d. | `test_coingecko_binance` (unit 8, integration 1), schedule test |
| Holiday calendars | `market_holidays` (fx, xau, boi), all seeded rows flagged as assumptions. Applied to sessions, gaps, derived candles and the BoI calendar. | `test_recorded_findings::test_seeded_holidays_are_labelled_assumptions`, `::test_fx_closed_on_christmas_session_day`, `::test_no_missing_candle_events_during_holiday`, `::test_israeli_rest_day_computation` |

### Test results (local, 2026-10-31, after findings A–I + CoinGecko/Binance/holidays)

- Backend: **222 passed** (unit + integration on TimescaleDB). ruff and mypy --strict clean. Real-trading guard clean.
- Frontend: Playwright **20 passed**.

## Open items needing the owner

- **Twelve Data Grow:** switch from Basic to Grow $29 before enabling ingestion on the VPS. Set `GMI_TWELVEDATA_CREDITS_PER_MINUTE=55` and `..._PER_DAY=0`.
- **BoI fallback publication time** 12:30 Israel time is based on one observation (12:21). Please confirm over a few days.
- **Holiday assumptions:** confirm the FX/gold closures (25 Dec, 1 Jan) against Twelve Data behaviour, and the BoI rest-day list.
- **Coinbase 1h candles:** the recorded 300 rows span 349 hours (about 50 missing). Please re-check from the VPS.
- **Re-record raw** from the VPS: BoI SDMX XML (byte-exact), CoinGecko, Binance, Coinbase book/product/time.
- **O1:** resolved. Use mid when bid/ask exist, otherwise last price, and record `price_type`.
- **G5:** read the Coinbase Market Data Terms of Use.
- **G6/G7 + live contracts:** once the Frankfurt VPS exists, run `scripts/check_provider_reachability.py` and `scripts/check_provider_contracts.py --save recorded/` and send the output.
