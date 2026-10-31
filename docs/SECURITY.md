# GMI – Security

## Implemented (Phase 1)

| Control | Implementation |
|---|---|
| Accounts | No public signup (D2). Users are created with `python -m app.cli create-user`. Roles: `admin`, `analyst`, `viewer`. |
| Password hashing | Argon2id (`argon2-cffi`). Minimum 12 characters. Rehash on login when parameters change. Unknown emails take the same verify time. |
| Sessions | Opaque 256-bit token in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie. Only its SHA-256 is stored. Fixed TTL (`GMI_SESSION_TTL_HOURS`). Revoked on logout and on password change. |
| CSRF | Synchronizer token. Its hash is stored on the session. Every non-GET request must send `X-CSRF-Token`. The readable `gmi_csrf` cookie holds the token. |
| RBAC | `require_roles(...)` dependency. Admin endpoints are admin-only (tested). |
| Rate limiting | Redis fixed window per client IP: login 10/min, API 300/min (configurable). nginx adds 20 r/s with burst 40. The limiter **fails open** if Redis is down (logged), so the owner is not locked out. Redis state shows in `/health/ready`. |
| Errors | RFC 9457 `application/problem+json`. No stack traces to clients. Login failures return one generic message. |
| Audit | `system_audit_logs` is append-only (trigger). It records logins, failed logins, logouts, user creation and password changes. |
| Secrets | Env vars only (`GMI_*`), typed as `SecretStr`. Never returned by any endpoint (tested). `.env` is git-ignored. `gitleaks` runs in CI. |
| Headers | `nosniff`, `Referrer-Policy`, `Cache-Control: no-store` on the API. nginx adds `X-Frame-Options: DENY` and `Permissions-Policy`. `noindex` metadata on the frontend. |
| API docs | Disabled when `GMI_ENVIRONMENT=production`. nginx also blocks `/api/docs`. |
| Real trading | Forbidden by design. `scripts/check_no_real_trading.py` fails CI on exchange order or withdrawal endpoints, trading credentials or ccxt. |
| Licensing | Individual data plans forbid third-party display, so the deployment is single-user and every page needs login. |

## Planned

HTTPS on the VPS (Phase 9 hardening, TLS described in `DEPLOYMENT.md`), backups and restore drills, a prompt-injection
defence for news-fed AI (Phase 6, plan §3.5), dependency audit and a threat model (Phase 9).
