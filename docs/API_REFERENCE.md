# GMI – API Reference (implemented endpoints)

Base path `/api/v1`. JSON in and out. Errors are `application/problem+json`:
`{type, title, status, detail, code, request_id, ...}`. Interactive docs are at `/api/docs` (non-production only).

Authentication uses the session cookie set by login. Every non-GET request needs the `X-CSRF-Token` header (the value of the `gmi_csrf` cookie).

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health/live` | – | Process is alive |
| GET | `/health/ready` | – | `{ok, checks:{database, redis}}` booleans; 503 if not ready |
| POST | `/api/v1/auth/login` | – (10/min/IP) | `{email, password}` → `{user, expires_at}` and sets cookies |
| POST | `/api/v1/auth/logout` | session + CSRF | Revokes the session (204) |
| GET | `/api/v1/auth/me` | session | Current user |
| GET | `/api/v1/instruments?include_secondary=true` | session | Instruments with validated configuration and provider mappings |
| GET | `/api/v1/instruments/{symbol}` | session | One instrument (case-insensitive symbol). 404 if unknown. |
| GET | `/api/v1/admin/providers` | admin | Provider status, licence notes and attribution (never credentials or raw config) |
| GET | `/api/v1/admin/jobs?limit=&offset=` | admin | Paginated `job_runs` (limit ≤ 200) |
| GET | `/api/v1/admin/system-health` | admin | Detailed readiness (TimescaleDB version, migration revision) |

Error codes: `not_authenticated` (401), `forbidden` (403, including a missing CSRF token), `not_found` (404),
`validation_error` (422), `rate_limited` (429 with `Retry-After`), `internal_error` (500).
