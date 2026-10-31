# GMI – Technical Plan

**Status:** **Approved 2026-10-31** with the decisions and changes in §0. Phase 1 is in progress.
**Source of requirements:** [`docs/SRS.md`](../SRS.md). Where §0 explicitly amends the SRS, §0 wins.

This document answers the ten items in SRS §25. Sections 1–10 are the original plan, edited where §0 changes them.

---

## 0. Approved decisions (2026-10-31)

### 0.1 Answers to open decisions

| ID | Decision |
|---|---|
| D1 | **Individual plans only.** Twelve Data **Grow** (individual plan, personal internal display) for USD/ILS and XAU/USD. **CoinGecko Demo** (free, attribution required) as the BTC reference. Free sources for everything else. |
| D2 | **Single user, personal non-commercial use.** One owner account plus admin. The schema stays multi-user, but there is **no public signup**. Accounts are created with a CLI command. |
| D3 | **EU cloud VPS (e.g. Frankfurt)**, so ingestion keeps running during local power or internet outages. |
| D4 | **Fed Broad Dollar Index** (FRED `DTWEXBGS`) for v1. It is always labelled as such and never called "DXY". No DXY licence. |
| D5 | **Claude via the Anthropic API**, behind the provider-independent `LLMClient` adapter. |
| D6 | Official sources (Fed, Bank of Israel, US agencies, Israel CBS) via RSS or APIs, plus reputable Arabic and English outlets via RSS. **Store summary and URL only, never full text.** |
| D7 | 1-minute data kept raw for **2 years, then compressed**. **1h and above kept forever.** |
| D8 | Default display timezone **`Asia/Gaza`** (not `Asia/Jerusalem`, whose DST dates can differ). Storage stays UTC. |
| D9 | **uv** (Python) and **pnpm** (frontend). |

### 0.2 Changes to the plan

1. **v1 forecast horizons: 1h, 4h, 24h, 7d, 30d.** 30d is **required for USD/ILS** because importer invoice planning depends on it. 15m, 3d, 90d and 180d are deferred.
2. **BTCUSD primary source: Coinbase Exchange public `BTC-USD` data.** Binance `BTCUSDT` is stored as a **separate secondary series** (its own instrument mapping, quote currency USDT). It is **never relabelled as USD** and never merged into BTCUSD candles. CoinGecko is the independent reference.
3. **The Importer Advisor moves to right after the market-data phase** (new Phase 3). It uses the **user-entered executable rate** as the price basis. It shows the **gap to the Bank of Israel representative rate** (with that rate's publication date) and **stores every entered rate** with its timestamp.
4. The full SRS is committed as `docs/SRS.md`.
5. **New required page: "Forecast Track Record" (سجل دقة التوقعات)**. It is v1 core scope, built in the Forecasting
   phase (Phase 5), in Arabic and English. The full requirement is in §0.4.

### 0.4 Forecast Track Record (requirement, added 2026-10-31)

**Ledger:** one row per forecast, newest first. Columns: instrument, horizon, issued_at, expires_at, reference price,
predicted price, lower and upper bound, bullish/neutral/bearish probabilities, model version and experimental flag.
After expiry it adds: actual price, absolute error, percentage error, direction correct (yes/no), inside range (yes/no),
Brier score and status.

**Automatic evaluation** by a Celery job at expiry. There is no manual entry.
- Actual price = the **last valid quote at or before `expires_at`, from the same provider** that supplied the
  forecast's reference price, **no older than 5 minutes**. Use its mid if bid/ask exist, otherwise its last price, and record `price_type`.
- If the market is closed or data is stale or missing at expiry, status = **`not_evaluable`** with a machine-readable reason
  (`market_closed`, `stale_data`, `no_data`, `provider_mismatch`). **The actual price is never estimated or filled.**
- USD/ILS rows also show the **Bank of Israel representative rate for that day** as a reference column. It is not used for scoring.

**Immutability:** forecast rows cannot be changed after issue. A DB trigger is created together with the `forecasts`
table in Phase 5. It allows only the `status` transition and blocks DELETE. Evaluation inserts into
`forecast_evaluations`. Statuses: **`pending`, `evaluated`, `not_evaluable`, `invalidated`**.

**Summary cards:** filterable by instrument, horizon, model and period (7/30/90 days/all). They show the number of forecasts,
directional accuracy %, MAE, MAPE, range coverage % compared with the nominal interval, and mean Brier score. Each metric is shown
side by side with the **random-walk baseline** (issued and evaluated by the same pipeline), plus "beats baseline: yes/no".
**Every metric shows its sample size. Below 30 evaluated forecasts the result is labelled "insufficient sample".**

**Charts:** predicted vs actual over time (per instrument and horizon, with the interval band), and a calibration chart
(forecast probability bins vs observed frequency, with the count per bin).

**Export:** ledger export to CSV and Excel (.xlsx), using the current filters.

**Tests:** evaluation job on labelled fixture data (normal, market-closed, stale and missing cases); immutability
trigger test; every metric (MAE, MAPE, directional accuracy, coverage, multi-class Brier) checked against hand-calculated values.

**Design consequences and open points:**
- **Direction needs a neutral band.** "Direction correct" and the 3-class Brier score need a definition of
  bullish/neutral/bearish outcomes. Each forecast stores its own `neutral_band` (for example ±k × expected volatility for that
  instrument and horizon) at issue time, so scoring never depends on a parameter chosen later. Brier = Σ over the 3
  classes of (p − o)² with p in [0,1] (range 0–2). The page states this definition.
- **Trading-time horizons (decided, §0.2a).** For USDILS and XAUUSD, horizons count open-market time on the
  session calendar (hours of open market for 1h/4h/24h, trading days for 7d/30d). BTCUSD uses calendar time.
  Stored per forecast: `horizon`, `horizon_basis` ∈ {trading_time, calendar_time} and `expires_at` (the calendar timestamp of
  the trading-time expiry). A **trading day** is one session day of the instrument's calendar (for FX/gold,
  17:00 New York to 17:00 New York with the market open). Adding N trading days lands at the same session-relative time N
  session days later, skipping closed days and holidays once holiday data exists. The exact algorithm and its tests
  ship in Phase 5 together with holiday calendars.
- **Price basis (decided, §0.2a).** Mid when the provider gives bid/ask, otherwise last. `price_type` and the provider are stored
  on each evaluation and shown in the ledger.
- **Coinbase BTC-USD** provides best bid/ask through its ticker, so BTCUSD mid quotes are expected to be available.

### 0.2a Answers received 2026-10-31 (after Phase 1)

| Topic | Decision |
|---|---|
| Twelve Data plan | Grow tiers are $29 / $49 / $79 by credits per minute. **$29 tier (55 credits/min)** is the target. The adapter must stay within 55 credits/min. Coverage of XAU/USD and USD/ILS is **unconfirmed until the owner's own key test**. The Twelve Data adapter is **on hold** until then. |
| Track Record price basis | Use **mid = (bid+ask)/2 when the provider gives bid and ask, otherwise the provider's last price**. Every evaluation stores `price_type` ∈ {mid, last} and the provider, and the ledger shows both. (Closes O1.) |
| Forecast horizons for USDILS and XAUUSD | **Measured in trading time** on the instrument's session calendar. 1h/4h/24h = that many **hours of open market**. 7d/30d = that many **trading days**. Each forecast stores both the trading-time expiry definition and its calendar timestamp (`expires_at`). **BTCUSD stays in calendar time (24/7).** If data is stale at expiry, the row is still `not_evaluable`. Expiries are **not** shifted to the next open. |
| Coinbase / Binance reachability | Checked from the Frankfurt VPS once it exists (`scripts/check_provider_reachability.py`). Binance stays secondary. |

### 0.3 Phase 2 entry gates (must be verified before Phase 2 code depends on them)

A pre-check on 2026-10-31 used web-search snippets only, because the provider sites were not reachable from the build sandbox. It found:

| Gate | Status | Notes |
|---|---|---|
| G1 Twelve Data Grow includes **XAU/USD** (real-time or delayed?) | **Unconfirmed** | Grow is listed as including commodities, but XAU/USD on Grow is not explicitly confirmed. Ask Twelve Data support or test with the key. |
| G2 Twelve Data Grow includes **USD/ILS** | **Unconfirmed** | The pair is in their catalogue. One snippet mentions real-time forex as an add-on. |
| G3 Twelve Data Grow price and credits | **Resolved** | $29 tier, 55 credits/min (owner). The adapter must respect the per-minute credit budget. |
| G4 Twelve Data licence fits use | **Consistent** | Support article: Basic/Grow data is for personal, non-commercial use and must not be displayed or redistributed to third parties. This matches D2. **The dashboard must not be shared with other people.** |
| G5 Coinbase Exchange market-data terms | **Unconfirmed** | Public endpoints need no auth (`api.exchange.coinbase.com`, about 10 req/s per IP). Use is governed by the Coinbase "Market Data Terms of Use". Personal-use wording not yet read. |
| G6 Coinbase reachable from EU VPS | **To test on VPS** | No geo restriction found. Servers are reported to be in AWS us-east-1, so expect latency from Frankfurt. |
| G7 Binance reachable from EU VPS | **At risk** | Binance limited EU services from July 2026 (MiCA). `api.binance.com` returns HTTP 451 in blocked regions. `data-api.binance.vision` is a spot-only market-data mirror. Binance is **optional/secondary**, so failure here does not block v1. |
| G8 CoinGecko Demo terms | **Consistent** | 30 calls/min, 10,000 calls/month, "Powered by CoinGecko API" link attribution required. Personal use is very likely fine. |

`scripts/check_provider_reachability.py` (added in Phase 2) will be run **on the VPS** to settle G6 and G7.

---

## 1. Repository inspection

| Item | Finding |
|---|---|
| Git state | Empty repository. No commits on `claude/sleepy-tesla-4a0xcf`, no files. |
| Existing code | None. Everything is greenfield. |
| Existing CI | None. |
| Dev container tooling | Python 3.13, Node 22, Docker 29 and PostgreSQL 16 client are available. |

*(Recorded at planning time. Phase 1 has since been implemented. See `IMPLEMENTATION_STATUS.md`.)*

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
- Provider-independent: an `LLMClient` interface. The first adapter is the Anthropic API (D5).
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
| USD/ILS intraday | **Twelve Data Grow** (D1) | Individual plan | Personal display only (G4). Plan coverage not yet confirmed (G2). Quotes are indicative and not a bank's executable rate. |
| XAU/USD spot | **Twelve Data Grow** (D1) | Individual plan | Plan coverage not yet confirmed (G1). LBMA benchmark prices are IBA-licensed and not used. |
| Gold futures | CME/COMEX via vendor | Paid | Exchange data fees apply. |
| **BTC/USD primary** spot, candles, order book | **Coinbase Exchange** public REST/WebSocket (`BTC-USD`) | Free | Market Data Terms of Use apply (G5). About 10 req/s per IP. |
| BTC/USDT secondary, funding, open interest | Binance public REST/WebSocket | Free | **Geo-restricted.** EU services limited since July 2026 (G7). Weight-based rate limits. Stored as a separate USDT series, never relabelled as USD. |
| BTC independent reference | CoinGecko API | Free tier / paid | Free (Demo) tier has low rate limits and needs attribution. Commercial use needs a paid plan. |
| Liquidations, ETF flows, on-chain | Coinglass, Glassnode, CryptoQuant (paid); mempool.space (free, limited) | Mostly paid | Optional modules, shown as "unavailable" when not configured (SRS §2.2). |
| US rates, yields, real yields, CPI, PCE | FRED API, BLS API, BEA API, US Treasury | Free (API key) | FRED series are revised. Point-in-time (ALFRED vintages) is needed for backtests. |
| Dollar index | **Fed Broad Dollar Index** (FRED `DTWEXBGS`) (D4) | Free | Daily and lagged. Labelled "Fed Broad Dollar Index", never "DXY". |
| Israel macro | Bank of Israel, Israel Central Bureau of Statistics | Free | Publication formats vary. Parsers need tests on real samples. |
| Gold positioning | CFTC Commitments of Traders | Free | Weekly, released with a lag (Tuesday data published Friday). |
| Gold ETF / central-bank flows | World Gold Council | Restricted | Terms limit automated reuse. Manual import or licence needed. |
| Economic calendar | Official release calendars (BLS, BEA, FOMC, BoI, CBS), or a paid calendar API | Free / paid | No reliable free consolidated calendar API exists. |
| News (EN/AR) | Official RSS (Fed, BoI, Treasury, SEC), GDELT, licensed news API | Free / paid | Copyright: store **title, summary, URL only**. NewsAPI's free tier is non-commercial and delayed. |
| Notifications | Telegram Bot API, SMTP provider | Free / low cost | Telegram rate limits per bot and chat. |
| LLM | Anthropic API (Claude) behind `LLMClient` (D5) | Paid per token | Latency and cost. Must degrade gracefully. |

---

## 6. Implementation roadmap

This follows the SRS §21 phases. Each phase ends with its acceptance criteria demonstrated and documented
in `IMPLEMENTATION_STATUS.md`. If a critical criterion fails, the next phase does not start.

| Phase | Gate (must be demonstrated) |
|---|---|
| 1 Foundation | `docker compose up` gives a healthy API, DB with migrations, auth with RBAC tests, instrument seed, CI green |
| 2 Market data | Entry gates G1–G8 resolved. All three instruments ingest real data (Twelve Data for USD/ILS and XAU/USD, Coinbase for BTC/USD, plus BoI reference and CoinGecko reference). Quality rules have unit tests. An outage simulation leaves the app running. Stale data disables signals. |
| **3 Importer Advisor** (moved up) | Uses the user-entered executable rate. Shows the gap to the BoI representative rate with its date. Entered rates are stored. Every calculation (now, installments, scenarios, worst case, break-even, shortfall) has tests in `Decimal`. Minimal AR/EN UI page. |
| 4 Analysis | Indicators match reference datasets within tolerance. No-lookahead test passes. News pipeline stores source plus URL. Economic releases have `released_at`. |
| 5 Forecasting | **Forecast Track Record page meets §0.4** (automatic evaluation, `not_evaluable` cases, sample-size labels, export). Baselines plus models for **1h, 4h, 24h, 7d and 30d** (30d mandatory for USD/ILS). Walk-forward report exists. Forecasts are immutable (trigger test). Evaluation job and calibration metrics run. The Importer Advisor gains forecast-based scenario ranges, labelled as forecasts and not hedges. |
| 6 AI | Structured AI output validated. Numeric cross-check test and prompt-injection test suite pass. |
| 7 Paper trading | Ledger reconciliation property tests, fill-rule tests (spread, slippage, gaps, SL/TP) |
| 8 Dashboard + notifications | All pages in AR/EN, RTL/LTR Playwright tests, Telegram/email delivery, reports with sources |
| 9 Hardening | Security review, load test, backup restore drill, UAT |

**v1 horizons (approved):** 1h, 4h, 24h, 7d and 30d (§0.2). 30d forecasts have few independent
out-of-sample points, so their evaluation reports must show the sample size, and they stay labelled
**experimental** until enough history exists.

---

## 7. Risks, unknowns and licensing

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **Twelve Data Grow coverage for USD/ILS and XAU/USD unconfirmed** (G1, G2) | Blocks intraday features for 2 of 3 instruments | Verify before Phase 2. If XAU/USD is missing on Grow, choose a different tier or source before writing the adapter. |
| R2 | Individual-plan licences forbid showing data to third parties | Legal exposure | Single-user deployment (D2), no public signup, login required for every page. Licence recorded per provider. |
| R3 | Binance EU restrictions (G7) | Secondary BTCUSDT series unavailable | Coinbase is primary. Binance is optional. Run the reachability script on the VPS. |
| R4 | DXY is proprietary | Different index from the SRS text | Fed Broad Dollar Index (D4), labelled everywhere. |
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

Provider interface (SRS §5.1) with capability flags. Adapters: BoI (official USD/ILS reference),
**Twelve Data** (USD/ILS and XAU/USD, credit-budgeted), **Coinbase Exchange** (BTC-USD primary, REST and WebSocket),
CoinGecko (BTC reference, with attribution in the UI), Binance (BTCUSDT secondary series, optional). Provider reachability script run on the VPS. Historical
backfill CLI. Validation rules, each with its own tests. Quote and candle repositories (hypertables).
Instrument data-status service. Provider health in `market_providers`. Live quote WebSocket channel. Endpoints:
`/markets/{symbol}/quote|candles|statistics`, `/admin/providers`. Development fixtures live only under
`backend/tests/fixtures/` and are labeled as such.

### Phase 3 – Importer Advisor (moved up, §0.2)

Inputs: invoice USD amount, due date, **user-entered executable buy rate** (with bank or source note),
available ILS balance, risk tolerance, transfer and conversion fees (fixed and %), optional installment
schedule. Every entered rate is stored in `importer_rate_entries` with `entered_at`. Outputs: full
purchase now, installment cost, scenario table over a user-defined rate grid, cost of waiting, worst-case exposure
within the chosen grid, break-even rate, ILS shortfall. Shows the **gap between the executable rate and
the latest Bank of Israel representative rate** (absolute and %), with that rate's publication date.
If no BoI rate is stored, it says so and shows no gap. All maths in `Decimal`, with tests. API:
`/importer/scenarios`, `/importer/compare-strategies`, `/importer/history`. Minimal AR/EN page.
Forecast-based ranges are added in Phase 5.

### Phase 4 – Analysis

Indicator library (all of SRS §7.1) with reference tests. Candle resampling with correct boundaries per
timeframe and session. Support/resistance, swings, Fibonacci, candlestick patterns, chart patterns
(SRS §7.2) with historical tests. Technical analysis JSON endpoint. Economic series ingestion (FRED,
BLS, BEA, BoI, CBS, CFTC) with `released_at`. Release calendar. Event-impact engine (historical reaction
statistics only where sample size allows). News ingestion, dedupe, language detection (AR/EN), relevance,
sentiment, impact scoring and claim-type labeling (fact, reported claim, opinion, speculation, unconfirmed).
Charting on asset pages.

### Phase 5 – Forecasting

Feature store with point-in-time joins. Baselines (random walk, persistence, historical volatility).
ARIMA/SARIMAX and GARCH. Random Forest, XGBoost and LightGBM. Monte Carlo. Walk-forward framework with
purging and embargo. Leakage tests. Model registry and promotion rules (must beat baseline out-of-sample).
Ensemble with validated weights and probability calibration (isotonic or Platt on validation folds).
Horizons 1h, 4h, 24h, 7d and 30d. **Forecast Track Record page (§0.4)**, including the evaluation-at-expiry job, baseline
side-by-side cards, calibration chart and CSV/XLSX export. Forecast issuance job with expiry and invalidation conditions. Immutable storage triggers. Evaluation job (MAE, RMSE,
MAPE where valid, directional accuracy, Brier, log loss, coverage, width, pinball). Forecast and
model-performance endpoints.

### Phase 6 – AI intelligence

LLM adapter. Prompt builders per asset. Output schema validation. Numeric grounding check. Injection
test corpus. Cross-asset engine (rolling correlations over several windows with sample size and confidence,
regime comparison, divergence alerts). AI analyst endpoint and scheduled narrative generation.

### Phase 7 – Paper trading

Accounts (USD/ILS currency). Orders (market, limit, stop, SL/TP). Fill engine with spread, slippage,
commission, sessions, gaps, partial fills and swap/financing. Positions with MFE and MAE. Ledger and reconciliation.
Risk metrics (equity, exposure, drawdown, win rate, profit factor, Sharpe with a minimum-sample guard).
Signal-based mode. Backtesting mode using the same fill engine on historical data.

### Phase 8 – Dashboard and notifications

All 20 pages. Global overview. Asset pages. Forecast center. Cross-asset dashboard. Alerts engine (all
SRS §16.1 types). Telegram and email delivery. Daily, weekly and monthly reports with timestamps and source links.
Full AR/EN coverage. Responsive layout.

### Phase 9 – Hardening

Threat model and security review. Dependency audit. Load test (k6 or Locust). Backup and restore drill.
Data-reliability chaos tests (provider down, stale feed, clock skew). Forecast validation report. UAT checklist.

---

## 9. What will NOT be built in v1

Real-money execution, broker or exchange private-API adapters, wallet functionality, withdrawals,
automated external account access (SRS §19.1). Any hardcoded prices or model metrics.
Synthetic market data outside labeled test fixtures.

---

## 10. Open decisions

All of D1–D9 are answered (see §0.1). The remaining open items are the Phase 2 entry gates in §0.3.
