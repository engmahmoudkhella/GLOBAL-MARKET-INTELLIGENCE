# Global Market Intelligence (GMI)

Multi-asset financial intelligence, forecasting and **paper-trading-only** platform for
**USD/ILS**, **XAU/USD** and **BTC/USD**.

> **Status: Phase 1 (foundation) implemented.** No market data, forecasts or trading yet. See
> [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) and
> [`docs/architecture/IMPLEMENTATION_PLAN.md`](docs/architecture/IMPLEMENTATION_PLAN.md).

> **No real-money trading.** Version 1 contains no broker or exchange execution of any kind.

## Documents

| Document | Purpose |
|---|---|
| `docs/SRS.md` | Software Requirements Specification v1.0 (source of truth) |
| `docs/architecture/IMPLEMENTATION_PLAN.md` | Architecture, dependencies, roadmap, risks, task breakdown, open decisions |
| `docs/database/DATABASE.md` | Database design proposal |
| `docs/DATA_SOURCES.md` | Providers, coverage, licensing, limitations |
| `docs/ARCHITECTURE.md` | What is implemented and how it fits together |
| `docs/API_REFERENCE.md` | Implemented endpoints |
| `docs/SECURITY.md` | Security controls |
| `docs/DEPLOYMENT.md` | Local development, tests, Docker Compose, VPS |
| `IMPLEMENTATION_STATUS.md` | What is done and what is pending |
| `CHANGELOG.md` | Changes |

Stack: Next.js + TypeScript, FastAPI, PostgreSQL + TimescaleDB, Redis, Celery, Docker Compose.

## Quick start

```bash
cp .env.example .env    # set POSTGRES_PASSWORD
docker compose up -d --build
docker compose run --rm api python -m app.cli create-user --email you@example.com --name Owner --role admin
```

Then open http://localhost:8080. For plain-HTTP local use, set `GMI_COOKIE_SECURE=false` in `.env`.
Details are in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

This is a personal, single-user deployment. The individual data-plan licences forbid showing provider data to anyone else.
