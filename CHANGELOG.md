# Changelog

## [Unreleased]

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
