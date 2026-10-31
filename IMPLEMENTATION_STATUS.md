# Implementation Status

Last updated: 2026-10-31. Phase numbering follows the approved plan (`docs/architecture/IMPLEMENTATION_PLAN.md` §0, §6).

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository inspection and technical plan | **Done. Approved 2026-10-31** with decisions D1–D9. |
| 1 | Foundation: repo layout, DB + migrations, auth/RBAC, instruments, Docker, CI, AR/EN shell | **Implemented. All Phase 1 checks pass locally (see below).** CI workflow added but not yet run on GitHub. |
| 2 | Market data (Twelve Data, Coinbase, BoI, CoinGecko, Binance secondary) | Not started. **Entry gates G1–G8 open** (plan §0.3). |
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
| CI green | **Pending.** `.github/workflows/ci.yml` is committed but has not run on GitHub yet. The same commands pass locally. |
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

## Open items needing the owner

- **G1/G2/G3:** confirm Twelve Data Grow covers XAU/USD and USD/ILS, and its price and credits (support ticket or test with your key).
- **O1 (plan §0.4):** whether Twelve Data provides bid/ask (needed for the mid-quote evaluation rule). Decide what to do if it doesn't.
- **G5:** read the Coinbase Market Data Terms of Use. **G6/G7:** run the reachability script on the VPS once it exists.
