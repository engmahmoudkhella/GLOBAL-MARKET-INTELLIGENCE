# GMI – Architecture (as implemented)

This page describes what **exists in the code**. The target design and roadmap are in
[`architecture/IMPLEMENTATION_PLAN.md`](architecture/IMPLEMENTATION_PLAN.md).

## Runtime topology (docker-compose)

```
browser ──HTTP(S)──> nginx ──/api, /health──> api (FastAPI, uvicorn)
                        └────────/*─────────> web (Next.js standalone)
                                              │ server-side fetch, forwards session cookie
                                              └──> api
api, worker (Celery), beat (Celery Beat) ──> db (PostgreSQL 16 + TimescaleDB)
                                         └─> redis (broker, rate limits)
migrate (one-shot): alembic upgrade head before api/worker/beat start
```

The browser sees **one origin**. It never calls third-party providers and never receives API keys.

## Backend modules (`backend/app`)

| Module | Status | Responsibility |
|---|---|---|
| `core/` | Phase 1 | settings (env only), JSON logging + request id, DB engine/session, Argon2id + tokens, problem+json errors, rate limiting, UTC clock, timezone validation |
| `models/` | Phase 1 | ORM models for Phase 1 tables (`users`, `user_sessions`, `instruments`, `market_providers`, `instrument_provider_symbols`, `system_audit_logs`, `job_runs`) |
| `auth/` | Phase 1 | login/logout/session resolution, CSRF, RBAC dependencies, CLI-only user creation |
| `audit/` | Phase 1 | append-only audit writer |
| `instruments/` | Phase 1 | `InstrumentConfig` schema (sessions, staleness, horizons…), read service |
| `jobs/` | Phase 1 | idempotent job runner backed by `job_runs` |
| `tasks/` | Phase 1–2 | Celery app, `system.heartbeat` (every 60 s), and ingestion tasks (Coinbase quote 15 s, candles 1m/1h/1d, BoI reference 30 min, freshness 60 s). Ingestion is scheduled **only when `GMI_INGESTION_ENABLED=true`**. |
| `markets/` | Phase 2 | session calendars (`MarketCalendar.is_open`, DST-aware), market-data API schemas |
| `providers/` | Phase 2 | provider interface (SRS §5.1) with capability flags; HTTP client (timeouts, retries, backoff, pacing); strict parsers; adapters: **Coinbase Exchange** (BTC-USD) and **Bank of Israel** (reference rates). Twelve Data on hold. |
| `quality/` | Phase 2 | data-quality rules (see `DATA_QUALITY.md`) |
| `ingestion/` | Phase 2 | provider → validation → storage. Provider health (active/degraded/down). Gap and staleness events. Freshness. |
| `api/` | Phase 1–2 | `/health/*`, `/api/v1/auth/*`, `/api/v1/instruments*`, `/api/v1/admin/{providers,jobs,system-health}` |
| `cli.py` | Phase 1–2 | `create-user`, `set-password`, `backfill-candles`, `backfill-reference` |

Rule: modules talk through their `service.py`. Routers stay thin.

## Frontend (`frontend/`)

Next.js App Router with `next-intl`. Routes are `/{ar|en}/...`, and Arabic is the default when the browser language
matches neither locale. `<html dir>` is `rtl` for Arabic and `ltr` for English. `proxy.ts` handles locale routing.
`app/[locale]/(app)/layout.tsx` checks the session server-side through `/api/v1/auth/me` and redirects to login.
Every signed-in page shows the "paper trading only" banner. All 21 navigation sections exist. Each one shows
"Not implemented yet" with its planned phase, except the overview, which lists instrument **configuration**
(horizons, sources). It shows no prices.

## Key invariants already enforced

- No public signup endpoint (tested).
- Audit log is append-only (DB trigger, tested).
- ORM models and migrations cannot drift (autogenerate-compare test).
- BTCUSD is mapped only to USD-quoted sources. BTCUSDT is a separate secondary instrument (tested).
- No real-money execution code (repository guard script, run in tests and CI).
- Secrets are `SecretStr` and never serialized (tested against every Phase 1 endpoint).
