# Implementation Status

Last updated: 2026-10-31 (Phase 2 groundwork). Phase numbering follows the approved plan (`docs/architecture/IMPLEMENTATION_PLAN.md` §0, §6).

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository inspection and technical plan | **Done. Approved 2026-10-31** with decisions D1–D9. |
| 1 | Foundation: repo layout, DB + migrations, auth/RBAC, instruments, Docker, CI, AR/EN shell | **Accepted.** GitHub CI green (run #2, 2026-10-31). |
| 2 | Market data (Twelve Data, Coinbase, BoI, CoinGecko, Binance secondary) | **In progress.** Groundwork done (see below). Twelve Data is on hold for the owner's coverage test. CoinGecko and Binance are not started. Live contracts are unverified until the VPS checks run. |
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
| Twelve Data adapter (USDILS, XAUUSD) | **On hold** | Waiting for the owner's coverage test |
| CoinGecko reference, Binance secondary, 4h aggregation, holiday calendars | Not started | — |

**Phase 2 is not complete.** Its acceptance gate ("all three instruments retrieve data") needs the Twelve Data adapter
and the live checks on the VPS.

### Test results (local, 2026-10-31, Phase 2 groundwork)

- Backend: **118 passed** (unit and integration on PostgreSQL 16 + TimescaleDB 2.31.0). ruff, ruff format and mypy --strict are clean.
- Frontend: eslint and tsc clean, build OK, Playwright **20 passed** (18 e2e + decimal-rounding unit test on 2 projects).

## Open items needing the owner

- **G1/G2:** the owner's Twelve Data key test for XAU/USD and USD/ILS quotes. Please include whether the quote response has `bid`/`ask` fields. G3 is resolved ($29, 55 credits/min).
- **O1:** resolved. Use mid when bid/ask exist, otherwise last price, and record `price_type`.
- **G5:** read the Coinbase Market Data Terms of Use.
- **G6/G7 + live contracts:** once the Frankfurt VPS exists, run `scripts/check_provider_reachability.py` and `scripts/check_provider_contracts.py --save recorded/` and send the output.
