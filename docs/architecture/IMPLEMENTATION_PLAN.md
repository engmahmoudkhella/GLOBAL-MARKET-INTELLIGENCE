# GMI – Initial Technical Plan (for review)

**Status:** Draft for review. No application code has been written yet.
**Date:** 2026-10-31
**Source of requirements:** GMI SRS v1.0 (to be committed as `docs/SRS.md`)

This document answers the ten items in SRS §25 ("Initial Claude Code master prompt").
Implementation starts only after this plan is reviewed and the open decisions in §10 are answered.

---

## 1. Repository inspection

| Item | Finding |
|---|---|
| Git state | Empty repository. No commits on `claude/sleepy-tesla-4a0xcf`, no files. |
| Existing code | None. Everything is greenfield. |
| Existing CI | None. |
| Dev container tooling | Python 3.13, Node 22, Docker 29 and PostgreSQL 16 client are available. |

Consequence: nothing can be assumed to be implemented (SRS §24 rule 4). Every feature in
`IMPLEMENTATION_STATUS.md` starts as **Not started**.

---

## 2. Technical dependencies

### 2.1 Runtime and platform

| Layer | Choice | Version target | Notes |
|---|---|---|---|
| Backend runtime | Python | **3.12** in Docker | 3.13 is in the dev container, but parts of the stats/ML stack (pmdarima, some arch wheels) may lag. Phase 1 pins one version after checking wheels. |
| API framework | FastAPI + Uvicorn | latest stable | Async API and WebSockets. |
| Schemas | Pydantic v2 | | Typed request and response contracts. |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | | Every schema change goes through a migration (SRS §6.2). |
| Database | PostgreSQL 16 + TimescaleDB 2.x | | Hypertables for quotes and candles, plus retention and compression policies. |
| Cache / broker | Redis 7 | | Celery broker, quote cache, rate-limit counters, WebSocket fan-out. |
| Jobs | Celery + Celery Beat | | Idempotent tasks keyed by (job, instrument, period). |
| Frontend | Next.js (App Router) + TypeScript | latest stable | |
| UI | Tailwind CSS + shadcn/ui (Radix) | | Radix primitives support RTL. |
| i18n | next-intl | | `ar` (RTL) and `en` (LTR), locale-prefixed routes. |
| Charts | TradingView Lightweight Charts | | Apache-2.0. Requires the TradingView attribution notice. |
| Reverse proxy | Nginx | | TLS termination in production. |
| Containers | Docker Compose | | `db`, `redis`, `api`, `worker`, `beat`, `web`, `nginx`. |

### 2.2 Quantitative and ML libraries

NumPy, Pandas, SciPy, statsmodels (ARIMA/SARIMAX), arch (GARCH), scikit-learn, XGBoost and LightGBM.
PyTorch is optional and only used for the experimental LSTM, in a separate `ml` extra so the API image stays small.
Indicators are **implemented in-house** in `backend/app/indicators/` with reference-dataset tests (SRS §22).
Libraries such as TA-Lib or pandas-ta are used only as **test oracles**, never as the production implementation,
so every formula is visible and tested.

### 2.3 Testing and quality

pytest, pytest-asyncio, hypothesis (property tests for accounting invariants), testcontainers
(real Postgres/Timescale in integration tests), Playwright (UI, RTL/LTR), ruff, mypy, ESLint, Prettier,
and GitHub Actions CI.

### 2.4 Financial-precision rule

Prices, balances, fees and P&L use `Decimal` in Python and `NUMERIC` in Postgres.
Floats are allowed only inside model training and inference (NumPy). Values are converted to `Decimal`
when they cross into the forecast, order or ledger layers.

---

## 3. Architecture plan

### 3.1 Style

A **modular monolith** (SRS §4.1). One FastAPI codebase is deployed as three process types
(`api`, `worker`, `beat`). Modules only talk to each other through service interfaces in
`app/<module>/service.py`. No module imports another module's repositories or ORM models directly.
This keeps later extraction into separate services possible.

### 3.2 Module map (backend/app)

```
core/            config (pydantic-settings), logging, security, db session, errors, clock (injectable UTC clock)
providers/       provider interface + adapters (boi, binance, coingecko, fred, <licensed fx/metals>, ...)
ingestion/       schedulers that call providers -> validation -> normalization -> repositories
quality/         data-quality rules (missing/duplicate/OHLC/outlier/stale/spread/timestamp) + status per instrument
indicators/      pure functions on pandas Series/DataFrames, no I/O
analysis/        technical analysis engine (structured JSON per SRS §7.3), pattern recognition
economics/       economic series, release calendar, event-impact engine
news/            ingestion, dedupe, language detection, relevance, sentiment, impact scoring
forecasting/     model interface, baselines, statistical/ML models, ensemble, forecast issuance, evaluation
cross_asset/     rolling correlations, regime comparison, divergence detection
ai_analyst/      LLM adapter interface, prompt builders, structured-output validation, injection guards
paper_trading/   accounts, orders, fill engine, positions, double-entry ledger, risk metrics
importer_advisor/ invoice scenarios, installment strategies, break-even
notifications/   dashboard, Telegram, email delivery + per-user preferences
reports/         daily/weekly/monthly report builders
audit/           audit log writer
api/v1/          routers per SRS §18; ws/ for live channels
tasks/           Celery task wrappers (thin; logic lives in modules)
```

`ml/` holds offline research and training code (datasets, features, walk-forward validation,
backtesting). Trained artifacts are registered in `model_registry` with a hash, training window
and validation metrics. The backend loads **only registered and approved** artifacts.

### 3.3 Market-engine isolation (SRS §4.3)

Each instrument is configured by one `InstrumentConfig` record (DB `instruments.configuration_json`,
validated by a Pydantic schema). It holds trading sessions, providers in priority order, tick size,
staleness thresholds, spread limits, indicator parameter sets, enabled horizons, enabled models and
paper-trading cost model. Engines are the same code run with different configs. Forecasts, signals,
model versions and performance are always keyed by `instrument_id`.

### 3.4 Data flow and the "no fabrication" guarantees

1. **Provider adapter** returns raw observations with `provider_id`, `observed_at` and `received_at`.
2. **Validation** classifies each observation as `verified`, `suspect` or `rejected` and writes
   `data_quality_events`. Gaps are **recorded, never filled**.
3. **Instrument data status** (`fresh`, `stale`, `degraded` or `down`) is derived from
   per-instrument thresholds. Signal and forecast issuance read this status. Anything other than
   `fresh` blocks high-confidence output and lowers `data_quality_score`.
4. **Point-in-time access:** every analytical read goes through an `as_of` parameter
   (`get_candles(instrument, tf, end <= as_of)`). The same code path serves live forecasting and
   backtesting, which is the main defense against look-ahead leakage. Economic data stores
   `released_at` (first publication time), not only the reference period, so revised figures cannot leak.
5. **Forecast issuance** writes an immutable row before the outcome is known. It stores input
   references (candle range, feature-set hash, model version). Postgres triggers reject `UPDATE`
   on issued forecast fields and allow only the `status` transition. Evaluations go into
   `forecast_evaluations`.

### 3.5 AI Chief Analyst

- The LLM receives **only structured, already-verified JSON** (quotes, indicators, model outputs
  and news items with IDs). It must return JSON matching the SRS §11.4 contract, validated by Pydantic.
- Every number in the LLM output is cross-checked against the input payload. Responses that
  introduce prices, levels or probabilities not present in the inputs are rejected.
- Scenario probabilities come from the forecasting engine, not from the LLM. The LLM explains them.
- News text is untrusted. It is passed inside delimited data fields with an explicit
  "data, not instructions" system policy, truncated, and stripped of markup. The LLM has **no tools**
  and cannot trigger actions (SRS §19).
- Provider-independent: an `LLMClient` interface with one adapter first. The adapter is chosen in
  open decision D5.
- If the LLM is unavailable, the platform still shows the structured analysis without narrative.

### 3.6 Paper trading engine

- An event-driven fill engine is evaluated on each new quote (BTC) or quote/candle (FX/gold).
  Market orders fill at **ask (buy) or bid (sell) plus a slippage model**, never at candle close (SRS §13.3).
- When only candles exist (no bid/ask), a configured spread model is applied and the fill is
  flagged `estimated_spread`.
- Session calendars block fills while the market is closed. Weekend gaps fill stops at the first
  available price (gap-through), not at the stop level.
- A **double-entry ledger** (`paper_transactions`) is the source of truth. Balances are derived and
  reconciled by a nightly job. Property-based tests assert that sum(ledger) equals balance.
- No broker adapter interface exists in v1. A CI check greps for forbidden patterns (exchange
  private endpoints, API-secret config keys for trading) to enforce SRS §19.1.

### 3.7 Frontend

Next.js App Router with `/[locale]/...` routes. Server components fetch from the API using a server-side
session, so no API keys or provider calls ever happen in the browser. Live prices come over a
WebSocket from the API. Every price or forecast widget shows **source, timestamp and freshness**.
Every paper-trading screen carries a persistent "SIMULATED" badge.

### 3.8 Security baseline

Argon2id password hashing. Session auth with httpOnly, Secure, SameSite cookies and CSRF tokens
for state-changing requests. RBAC (`admin`, `analyst`, `viewer`). Row-level ownership checks on
every paper-account and alert query. Rate limiting with Redis. Secrets only from env or a secret store.
Provider calls have timeouts and retry with exponential backoff and jitter. `gitleaks` runs in CI.

---

## 4. Database design

The full proposal is in [`docs/database/DATABASE.md`](../database/DATABASE.md). It keeps every SRS §6.1 table and adds the
tables needed to satisfy other requirements:

| Added table | Why |
|---|---|
| `instrument_provider_symbols` | Provider-native symbol mapping (SRS §5.4) |
| `data_quality_events` | Gap, outlier, stale and outage records (SRS §5.3) |
| `economic_series`, `economic_observations` | Standardized economic data model with release timestamps (SRS §8.1, no leakage) |
| `technical_patterns` | Pattern detections with boundaries, confirmation and invalidation (SRS §7.2) |
| `forecast_inputs` | Reproducible input references per forecast (SRS §17.3) |
| `paper_fills` | Partial fills (SRS §13.3) |
| `importer_scenarios` | Importer advisor history (SRS §18 `/importer/history`) |
| `notification_deliveries` | Delivery status and retries per channel |
| `job_runs` | Idempotency and monitoring for Celery jobs |
| `user_sessions` | Server-side sessions and revocation |

Hypertables: `market_quotes`, `market_candles` and `technical_indicators`, with compression and retention
policies (for example raw 1-minute data kept for N months, then only aggregates). Retention values are open decision D7.

---

## 5. External APIs and their limitations

Details and licensing are in [`docs/DATA_SOURCES.md`](../DATA_SOURCES.md). Summary:

| Need | Candidate | Cost | Main limitation |
|---|---|---|---|
| USD/ILS official reference | Bank of Israel (public series / SDMX API) | Free | Once-daily **representative rate**. It is not an executable quote and has no intraday data. |
| USD/ILS intraday bid/ask | Licensed FX vendor (e.g. OANDA, Twelve Data, Polygon.io, Alpha Vantage premium) | Paid | Shekel liquidity is thin outside Israeli/European hours. Redistribution in a multi-user UI usually needs a display licence. |
| XAU/USD spot | Licensed metals or multi-asset vendor (same shortlist) | Paid | No free source provides reliable intraday bid/ask with redistribution rights. LBMA benchmark prices are IBA-licensed. |
| Gold futures | CME/COMEX via vendor | Paid | Exchange data fees apply. |
| BTC/USD spot, candles, order book, funding, open interest | Binance public REST/WebSocket | Free | **Geo-restricted** (blocked from US IPs, which matters for the hosting region). Weight-based rate limits. BTCUSDT is not BTC/USD, so the USDT basis must be documented. Terms of use apply to redistribution. |
| BTC independent reference | CoinGecko API | Free tier / paid | Free (Demo) tier has low rate limits and needs attribution. Commercial use needs a paid plan. |
| Liquidations, ETF flows, on-chain | Coinglass, Glassnode, CryptoQuant (paid); mempool.space (free, limited) | Mostly paid | Optional modules, shown as "unavailable" when not configured (SRS §2.2). |
| US rates, yields, real yields, CPI, PCE | FRED API, BLS API, BEA API, US Treasury | Free (API key) | FRED series are revised. Point-in-time (ALFRED vintages) is needed for backtests. |
| Dollar index | ICE **DXY** is proprietary and licensed | Paid | Free alternative: Fed Broad Dollar Index (FRED `DTWEXBGS`, daily, lagged). The UI must label which one is used. |
| Israel macro | Bank of Israel, Israel Central Bureau of Statistics | Free | Publication formats vary. Parsers need tests on real samples. |
| Gold positioning | CFTC Commitments of Traders | Free | Weekly, released with a lag (Tuesday data published Friday). |
| Gold ETF / central-bank flows | World Gold Council | Restricted | Terms limit automated reuse. Manual import or licence needed. |
| Economic calendar | Official release calendars (BLS, BEA, FOMC, BoI, CBS), or a paid calendar API | Free / paid | No reliable free consolidated calendar API exists. |
| News (EN/AR) | Official RSS (Fed, BoI, Treasury, SEC), GDELT, licensed news API | Free / paid | Copyright: store **title, summary, URL only**. NewsAPI's free tier is non-commercial and delayed. |
| Notifications | Telegram Bot API, SMTP provider | Free / low cost | Telegram rate limits per bot and chat. |
| LLM | Provider-independent adapter | Paid per token | Latency and cost. Must degrade gracefully. |

---

## 6. Implementation roadmap

This follows the SRS §21 phases. Each phase ends with its acceptance criteria demonstrated and documented
in `IMPLEMENTATION_STATUS.md`. If a critical criterion fails, the next phase does not start.

| Phase | Weeks | Gate (must be demonstrated) |
|---|---|---|
| 1 Foundation | 1–2 | `docker compose up` gives a healthy API, DB with migrations, auth with RBAC tests, instrument seed, CI green |
| 2 Market data | 3–4 | All three instruments ingest real data from at least one provider. Quality rules have unit tests. An outage simulation leaves the app running. Stale data disables signals. |
| 3 Analysis | 5–6 | Indicators match reference datasets within tolerance. No-lookahead test passes. News pipeline stores source plus URL. Economic releases have `released_at`. |
| 4 Forecasting | 7–9 | Baselines plus at least one model per instrument for at least two horizons. Walk-forward report exists. Forecasts are immutable (trigger test). Evaluation job and calibration metrics run. |
| 5 AI | 10 | Structured AI output validated. Numeric cross-check test and prompt-injection test suite pass. |
| 6 Paper trading + importer | 11–12 | Ledger reconciliation property tests, fill-rule tests (spread, slippage, gaps, SL/TP) and importer calculations tested |
| 7 Dashboard + notifications | 13–14 | All pages in AR/EN, RTL/LTR Playwright tests, Telegram/email delivery, reports with sources |
| 8 Hardening | 15–16 | Security review, load test, backup restore drill, UAT |

**Recommended scope reduction for the first forecasting release:** start with horizons
**1h, 24h and 7d** for all three instruments. Add 15m/4h after the intraday data licence is confirmed,
and 30d/90d/180d once enough history and point-in-time macro data exist. Long horizons have very few
independent test samples, so honest evaluation there is weak (SRS §3 allows this).

---

## 7. Risks, unknowns and licensing

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **No licensed intraday feed for USD/ILS and XAU/USD yet** | Blocks intraday features, paper fills and 15m–4h forecasts for 2 of 3 instruments | Decide vendor early (D1). Until then, run daily-only mode using BoI and a free daily source, clearly labeled. |
| R2 | Redistribution rights: showing vendor data to multiple users is often a separate licence | Legal exposure | Record the licence per provider in `DATA_SOURCES.md`. Restrict the UI to licensed users. |
| R3 | Binance geo-blocking from the hosting region | BTC ingestion fails | Choose hosting region accordingly. Keep CoinGecko or another exchange as a fallback adapter. |
| R4 | DXY is proprietary | Feature unavailable or unlicensed | Use the Fed Broad Dollar Index, labeled, unless DXY is licensed. |
| R5 | Low inherent predictability (FX and BTC are close to random walk at short horizons) | Models may not beat baselines | This is expected and must be reported honestly. Forecasts that fail to beat the baseline are labeled **experimental** (SRS §10.5). |
| R6 | Look-ahead leakage through revised macro data or misaligned candles | Inflated backtests | `as_of` access layer, `released_at` timestamps, ALFRED vintages, leakage unit tests |
| R7 | Prompt injection through news | Corrupted AI output | Tool-less LLM, delimiting, numeric cross-check, injection test corpus |
| R8 | Israeli market calendar (holidays, business-week changes) and FX session edges | Wrong staleness flags and fills | Session calendars are data, not code. Each has an override table and tests. |
| R9 | LLM cost and latency | Budget | Cache per (instrument, data snapshot hash). Generate narrative on schedule, not per page view. |
| R10 | Schedule: 12–16 weeks assumes a team; a single developer plus AI assistant is slower | Timeline | Gate-based phases. Priority is correctness over breadth. |
| R11 | Regulatory: signals and importer advice could be read as investment advice in some jurisdictions | Legal | Persistent disclaimers. Language that never guarantees outcomes. Legal review before any public launch. |

**Unknowns that need your input** are listed in §10.

---

## 8. Phase-by-phase task breakdown

### Phase 1 – Foundation (next step after approval)

1. Monorepo layout per SRS §20: `backend/`, `frontend/`, `ml/`, `infrastructure/`, `docs/`, `scripts/`.
2. `backend/pyproject.toml` (uv or Poetry), ruff, mypy, pytest config.
3. `core/config.py` (pydantic-settings), `.env.example` with every variable documented and no real values.
4. Structured JSON logging with request IDs. `/health/live` and `/health/ready` (DB and Redis checks).
5. SQLAlchemy base, Alembic setup, TimescaleDB extension migration.
6. Migrations: `users`, `user_sessions`, `instruments`, `instrument_provider_symbols`,
   `market_providers`, `system_audit_logs`, `job_runs`.
7. Instrument seed (USDILS, XAUUSD, BTCUSD) with a validated `InstrumentConfig` schema.
   The seed holds **configuration only, no prices**.
8. Auth: register (admin-only invite), login, logout, `me`. Argon2id. Session cookies, CSRF, RBAC dependency.
9. Rate limiting middleware. Structured error model (RFC 7807 problem+json).
10. `GET /api/v1/instruments`, `GET /api/v1/instruments/{symbol}`.
11. Audit log service, used by auth and admin actions.
12. Celery worker and beat skeleton with one idempotent heartbeat task recorded in `job_runs`.
13. Frontend skeleton: Next.js, Tailwind, next-intl (`ar` RTL and `en` LTR), login page, layout with the
    20-item navigation (empty states saying "Not implemented yet", **no placeholder numbers**).
14. Docker Compose: `db` (timescale image), `redis`, `api`, `worker`, `beat`, `web`, `nginx`.
15. GitHub Actions: lint, type-check, unit tests, integration tests with Timescale service, gitleaks,
    and the forbidden-real-trading pattern check.
16. Docs: README, ARCHITECTURE, DATABASE, SECURITY, DEPLOYMENT (dev), IMPLEMENTATION_STATUS, CHANGELOG.

Tests: config loading, password hashing, login/logout/session expiry, RBAC denial, rate limiting,
migration up/down on real Timescale, instrument endpoints, health checks, Playwright smoke test (AR and EN render with the correct `dir`).

### Phase 2 – Market data

Provider interface (SRS §5.1) with capability flags. Adapters: BoI (official USD/ILS), Binance (BTC REST
and WebSocket), CoinGecko (BTC reference), plus licensed FX/metals vendor(s) once chosen. Historical
backfill CLI. Validation rules, each with its own tests. Quote and candle repositories (hypertables).
Instrument data-status service. Provider health in `market_providers`. Live quote WebSocket channel. Endpoints:
`/markets/{symbol}/quote|candles|statistics`, `/admin/providers`. Development fixtures live only under
`backend/tests/fixtures/` and are labeled as such.

### Phase 3 – Analysis

Indicator library (all of SRS §7.1) with reference tests. Candle resampling with correct boundaries per
timeframe and session. Support/resistance, swings, Fibonacci, candlestick patterns, chart patterns
(SRS §7.2) with historical tests. Technical analysis JSON endpoint. Economic series ingestion (FRED,
BLS, BEA, BoI, CBS, CFTC) with `released_at`. Release calendar. Event-impact engine (historical reaction
statistics only where sample size allows). News ingestion, dedupe, language detection (AR/EN), relevance,
sentiment, impact scoring and claim-type labeling (fact, reported claim, opinion, speculation, unconfirmed).
Charting on asset pages.

### Phase 4 – Forecasting

Feature store with point-in-time joins. Baselines (random walk, persistence, historical volatility).
ARIMA/SARIMAX and GARCH. Random Forest, XGBoost and LightGBM. Monte Carlo. Walk-forward framework with
purging and embargo. Leakage tests. Model registry and promotion rules (must beat baseline out-of-sample).
Ensemble with validated weights and probability calibration (isotonic or Platt on validation folds).
Forecast issuance job with expiry and invalidation conditions. Immutable storage triggers. Evaluation job (MAE, RMSE,
MAPE where valid, directional accuracy, Brier, log loss, coverage, width, pinball). Forecast and
model-performance endpoints.

### Phase 5 – AI intelligence

LLM adapter. Prompt builders per asset. Output schema validation. Numeric grounding check. Injection
test corpus. Cross-asset engine (rolling correlations over several windows with sample size and confidence,
regime comparison, divergence alerts). AI analyst endpoint and scheduled narrative generation.

### Phase 6 – Paper trading and importer advisor

Accounts (USD/ILS currency). Orders (market, limit, stop, SL/TP). Fill engine with spread, slippage,
commission, sessions, gaps, partial fills and swap/financing. Positions with MFE and MAE. Ledger and reconciliation.
Risk metrics (equity, exposure, drawdown, win rate, profit factor, Sharpe with a minimum-sample guard).
Signal-based mode. Backtesting mode using the same fill engine on historical data. Importer
advisor: full purchase now, installments, waiting scenarios, worst case, break-even, shortfall, history.

### Phase 7 – Dashboard and notifications

All 20 pages. Global overview. Asset pages. Forecast center. Cross-asset dashboard. Alerts engine (all
SRS §16.1 types). Telegram and email delivery. Daily, weekly and monthly reports with timestamps and source links.
Full AR/EN coverage. Responsive layout.

### Phase 8 – Hardening

Threat model and security review. Dependency audit. Load test (k6 or Locust). Backup and restore drill.
Data-reliability chaos tests (provider down, stale feed, clock skew). Forecast validation report. UAT checklist.

---

## 9. What will NOT be built in v1

Real-money execution, broker or exchange private-API adapters, wallet functionality, withdrawals,
automated external account access (SRS §19.1). Any hardcoded prices or model metrics.
Synthetic market data outside labeled test fixtures.

---

## 10. Open decisions (need your answers before or during Phase 1–2)

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Licensed FX and metals data vendor and budget for USD/ILS and XAU/USD intraday bid/ask | Shortlist OANDA, Twelve Data and Polygon.io. Compare ILS coverage, history depth and display licence. |
| D2 | Users: single owner, small team, or public multi-user? | Start with a small invite-only team. This decides the licensing scope (R2). |
| D3 | Hosting provider and region | Non-US region so Binance public endpoints work (R3). |
| D4 | DXY: license ICE DXY or use the Fed Broad Dollar Index? | Fed Broad index first, clearly labeled. |
| D5 | LLM provider for the AI analyst | Any. The adapter keeps it swappable. |
| D6 | News sources, especially Arabic-language outlets and any paid news API | Official sources plus GDELT first. Add licensed feeds later. |
| D7 | Data retention for 1-minute data and quotes | Keep 1-minute data for 24 months compressed and quotes for 90 days. Keep aggregates indefinitely. |
| D8 | Default display timezone | `Asia/Jerusalem`, configurable per user |
| D9 | Package manager preference (uv or Poetry; pnpm or npm) | uv and pnpm |
