# Changelog

## [Unreleased]

### Phase 2 – groundwork (2026-10-31)
#### Added
- Provider interface with capability flags. Shared HTTP client (timeouts, exponential backoff with jitter, Retry-After, pacing).
  Strict response parsing (`ProviderDataError` on any contract deviation).
- Coinbase Exchange adapter (BTC-USD ticker, candles with 300-bucket pagination, L2 book, product status, server time).
- Bank of Israel adapter (latest representative rates via PublicApi, history via SDMX `RER_<CUR>_ILS`). Reference rates only.
- DST-aware session calendars. Data-quality rules (OHLC, crossed or missing quotes, timestamp skew, misalignment,
  duplicates, MAD outliers, abnormal spread, missing-candle gaps, staleness, outages).
- Migration `0003_market_data`: `market_quotes` and `market_candles` hypertables with compression and retention per D7,
  `data_quality_events`, `official_reference_rates`.
- Ingestion service with provider health tracking, immutable completed candles, gap and staleness events, freshness.
- Celery ingestion tasks (off unless `GMI_INGESTION_ENABLED=true`). CLI `backfill-candles`, `backfill-reference`.
- API: `/api/v1/markets/{symbol}/quote|candles|reference-rates`.
- Overview shows per-instrument data status, and a verified price (exact decimal rounding, timezone-labelled time) when one exists.
- Scripts: `check_provider_reachability.py`, `check_provider_contracts.py` (run on the VPS).
- Docs: `DATA_QUALITY.md`. Plan §0.2a records the owner's answers (Twelve Data tier, mid/last price type, trading-time horizons).

#### Fixed
- CI e2e job hang: `wait-on` used HEAD, which FastAPI rejects with 405. Now uses `http-get://` with timeouts, and jobs have time limits.


### Phase 1 – Foundation (2026-10-31)
#### Added
- Backend (FastAPI, SQLAlchemy 2, Alembic, psycopg 3, uv): settings from env, JSON logging with request ids,
  problem+json errors, Argon2id passwords, cookie sessions (hashed tokens), CSRF synchronizer token, RBAC,
  Redis/in-memory rate limiting, append-only audit log, idempotent job runner, Celery worker + beat with heartbeat.
- Migrations `0001_foundation` (TimescaleDB extension, users, sessions, instruments, providers, symbol mappings,
  audit log with append-only trigger, job runs) and `0002_seed_reference_data` (USDILS, XAUUSD, BTCUSD,
  BTCUSDT secondary; providers BoI, Twelve Data, Coinbase, CoinGecko, Binance; configuration only).
- API: `/health/live`, `/health/ready`, `/api/v1/auth/{login,logout,me}`, `/api/v1/instruments[/{symbol}]`,
  `/api/v1/admin/{providers,jobs,system-health}`.
- CLI: `create-user`, `set-password` (no public signup).
- Frontend (Next.js 16, next-intl, Tailwind 4): Arabic (RTL, default) / English (LTR), login, authenticated shell,
  21 navigation sections including Forecast Track Record, paper-trading-only banner, instrument configuration overview.
- Docker Compose stack (db, redis, migrate, api, worker, beat, web, nginx), Dockerfiles, nginx config, `.env.example`.
- CI workflow: guards (real-trading pattern scan, gitleaks), backend lint/types/tests on TimescaleDB, frontend
  lint/types/build/Playwright.
- `scripts/check_no_real_trading.py`.
- Docs: `docs/SRS.md`, ARCHITECTURE, SECURITY, DEPLOYMENT, API_REFERENCE. Plan updated with approved decisions,
  Phase 2 entry gates, Importer Advisor moved to Phase 3, v1 horizons, Coinbase as BTC primary, and the
  Forecast Track Record requirement.

### Planning
### Added
- Initial technical plan (`docs/architecture/IMPLEMENTATION_PLAN.md`).
- Database design proposal (`docs/database/DATABASE.md`).
- Data sources and licensing assessment (`docs/DATA_SOURCES.md`).
- README, implementation status and changelog.
