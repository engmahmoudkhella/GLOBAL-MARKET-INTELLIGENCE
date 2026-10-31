from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.conftest import TEST_PASSWORD, login, make_user

pytestmark = pytest.mark.integration


def test_no_public_signup_endpoint(client):
    for path in ("/api/v1/auth/register", "/api/v1/auth/signup", "/api/v1/users"):
        assert client.post(path, json={}).status_code in (404, 405)


def test_login_me_logout_flow(client, db):
    make_user(db)
    csrf = login(client)
    cookie_header = client.cookies
    assert "gmi_session" in cookie_header

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "owner@example.com" and "password_hash" not in body

    # Logout without CSRF header is refused
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    r = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403

    r = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_revoked_session_token_cannot_be_reused(client, db):
    make_user(db)
    csrf = login(client)
    token = client.cookies["gmi_session"]
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    client.cookies.set("gmi_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_cookie_flags(client, db):
    make_user(db)
    r = client.post(
        "/api/v1/auth/login", json={"email": "OWNER@example.com", "password": TEST_PASSWORD}
    )
    assert r.status_code == 200  # email is case-insensitive
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("gmi_session="))
    csrf_cookie = next(c for c in cookies if c.startswith("gmi_csrf="))
    assert "HttpOnly" in session_cookie and "SameSite=strict" in session_cookie
    assert "HttpOnly" not in csrf_cookie


@pytest.mark.parametrize(
    "email,password",
    [
        ("owner@example.com", "wrong password here"),
        ("nobody@example.com", TEST_PASSWORD),
    ],
)
def test_bad_credentials_give_identical_generic_error(client, db, email, password):
    make_user(db)
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["detail"] == "Invalid email or password"
    assert (
        db.execute(
            text("SELECT count(*) FROM system_audit_logs WHERE action='auth.login_failed'")
        ).scalar()
        == 1
    )


def test_inactive_user_cannot_login(client, db):
    make_user(db)
    db.execute(text("UPDATE users SET is_active=false"))
    db.commit()
    r = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD}
    )
    assert r.status_code == 401


def test_expired_session_rejected(client, db):
    make_user(db)
    login(client)
    db.execute(
        text("UPDATE user_sessions SET expires_at = now() - :d"), {"d": timedelta(seconds=1)}
    )
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_tokens_stored_hashed(client, db):
    make_user(db)
    login(client)
    raw = client.cookies["gmi_session"]
    stored = db.execute(text("SELECT token_hash FROM user_sessions")).scalar()
    assert stored != raw and len(stored) == 64


def test_login_rate_limited(client, db, monkeypatch):
    make_user(db)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_login_per_minute", 3)
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "nope"})
    r = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD}
    )
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited" and "Retry-After" in r.headers


def test_validation_errors_are_problem_json(client, db):
    r = client.post("/api/v1/auth/login", json={"email": "a@b.c"})
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"


def test_password_change_revokes_sessions(client, db):
    from app.auth import service
    from app.models import User

    make_user(db)
    login(client)
    user = db.query(User).one()
    service.set_password(db, user, "another long password")
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
