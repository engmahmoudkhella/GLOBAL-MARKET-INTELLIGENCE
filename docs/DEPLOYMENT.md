# GMI – Deployment

## Local development (no Docker)

Requirements: Python 3.12 via `uv`, Node 22 with `pnpm`, and a PostgreSQL 16 + TimescaleDB server and Redis.

```bash
docker run -d --name gmi-db -e POSTGRES_USER=gmi -e POSTGRES_PASSWORD=gmi -e POSTGRES_DB=gmi -p 5432:5432 timescale/timescaledb:2.31.0-pg16
docker run -d --name gmi-redis -p 6379:6379 redis:7-alpine
cd backend
uv sync
export GMI_COOKIE_SECURE=false GMI_ENVIRONMENT=development
uv run alembic upgrade head
uv run python -m app.cli create-user --email you@example.com --name "Owner" --role admin
uv run uvicorn app.main:app --reload --port 8000
# in another shell
cd frontend && pnpm install && pnpm dev   # http://localhost:3000 (proxies /api to :8000)
```

### Tests

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://gmi:gmi@localhost:5432/gmi uv run pytest   # unit + integration
uv run ruff check . && uv run ruff format --check . && uv run mypy app
cd ../frontend
pnpm lint && pnpm typecheck && pnpm build
E2E_EMAIL=you@example.com E2E_PASSWORD='...' pnpm test:e2e   # needs the stack running on :3000
```

Without `TEST_DATABASE_URL` the integration tests are skipped locally. CI fails if any test is skipped.

## Docker Compose (single VPS, decision D3: EU, e.g. Frankfurt)

```bash
cp .env.example .env        # set POSTGRES_PASSWORD; keep GMI_COOKIE_SECURE=true behind HTTPS
docker compose up -d --build
docker compose run --rm api python -m app.cli create-user --email you@example.com --name Owner --role admin
curl -s localhost:8080/health/ready
```

Services: `db`, `redis`, `migrate` (one-shot `alembic upgrade head`), `api`, `worker`, `beat`, `web` and `nginx`.
Only nginx publishes a port (`GMI_HTTP_PORT`, default 8080). The database and Redis are reachable only on the compose network.

> For plain-HTTP testing on localhost, set `GMI_COOKIE_SECURE=false`, otherwise the browser will not
> send the session cookie. Never do this on the public VPS.

### HTTPS (required before real use)

Terminate TLS in nginx with a Let's Encrypt certificate (certbot or an ACME companion) and redirect port 80 to 443.
The production override with the 443 server block is a Phase 9 hardening task. Until then, reach the VPS only
through an SSH tunnel (`ssh -L 8080:localhost:8080 vps`).

### Provider reachability (Phase 2 entry gates G6/G7)

Run `scripts/check_provider_reachability.py` **on the VPS** once it exists (Phase 2) to confirm that Coinbase, Binance,
Twelve Data, CoinGecko and the Bank of Israel are reachable from the EU region.
