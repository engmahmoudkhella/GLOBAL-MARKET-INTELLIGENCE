# Global Market Intelligence (GMI)

Multi-asset financial intelligence, forecasting and **paper-trading-only** platform for
**USD/ILS**, **XAU/USD** and **BTC/USD**.

> **Status: planning.** No application code exists yet. See
> [`docs/architecture/IMPLEMENTATION_PLAN.md`](docs/architecture/IMPLEMENTATION_PLAN.md) and
> [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md).

> **No real-money trading.** Version 1 contains no broker or exchange execution of any kind.

## Documents

| Document | Purpose |
|---|---|
| `docs/SRS.md` | Software Requirements Specification v1.0 (source of truth, to be added) |
| `docs/architecture/IMPLEMENTATION_PLAN.md` | Architecture, dependencies, roadmap, risks, task breakdown, open decisions |
| `docs/database/DATABASE.md` | Database design proposal |
| `docs/DATA_SOURCES.md` | Providers, coverage, licensing, limitations |
| `IMPLEMENTATION_STATUS.md` | What is done and what is pending |
| `CHANGELOG.md` | Changes |

Planned stack: Next.js + TypeScript, FastAPI, PostgreSQL + TimescaleDB, Redis, Celery, Docker Compose.
