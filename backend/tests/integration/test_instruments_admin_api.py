import pytest

from tests.integration.conftest import login, make_user

pytestmark = pytest.mark.integration

SECRET = "sk-test-should-never-leak-123"


def test_instruments_require_auth(client):
    r = client.get("/api/v1/instruments")
    assert r.status_code == 401
    assert r.json()["code"] == "not_authenticated"


def test_list_and_get_instruments(client, db):
    make_user(db, role="viewer")
    login(client)
    r = client.get("/api/v1/instruments")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 4
    assert [i["symbol"] for i in data["items"]][:3] == ["USDILS", "XAUUSD", "BTCUSD"]

    primary = client.get("/api/v1/instruments", params={"include_secondary": False}).json()
    assert {i["symbol"] for i in primary["items"]} == {"USDILS", "XAUUSD", "BTCUSD"}

    one = client.get("/api/v1/instruments/btcusd").json()
    assert one["symbol"] == "BTCUSD" and one["quote_currency"] == "USD"
    assert one["providers"][0]["provider"] == "coinbase"
    assert one["providers"][0]["provider_symbol"] == "BTC-USD"

    missing = client.get("/api/v1/instruments/EURUSD")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_admin_endpoints_rbac(client, db):
    make_user(db, email="viewer@example.com", role="viewer")
    login(client, "viewer@example.com")
    for path in ("/api/v1/admin/providers", "/api/v1/admin/jobs", "/api/v1/admin/system-health"):
        r = client.get(path)
        assert r.status_code == 403, path


def test_admin_providers_and_jobs(client, db):
    make_user(db)
    login(client)
    providers = client.get("/api/v1/admin/providers").json()
    assert {p["provider_name"] for p in providers} == {
        "boi",
        "twelvedata",
        "coinbase",
        "coingecko",
        "binance",
    }
    assert all("configuration_json" not in p for p in providers)
    jobs = client.get("/api/v1/admin/jobs", params={"limit": 10}).json()
    assert jobs["items"] == [] and jobs["limit"] == 10 and jobs["total"] == 0
    assert client.get("/api/v1/admin/jobs", params={"limit": 1000}).status_code == 422


def test_secrets_never_returned(client, db, monkeypatch):
    from pydantic import SecretStr

    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "twelvedata_api_key", SecretStr(SECRET))
    monkeypatch.setattr(s, "anthropic_api_key", SecretStr(SECRET))
    make_user(db)
    login(client)
    for path in (
        "/api/v1/instruments",
        "/api/v1/instruments/USDILS",
        "/api/v1/admin/providers",
        "/api/v1/admin/system-health",
        "/api/v1/auth/me",
        "/health/ready",
    ):
        assert SECRET not in client.get(path).text, path


def test_health_endpoints(client, db):
    assert client.get("/health/live").json() == {"status": "alive"}
    r = client.get("/health/ready")
    body = r.json()
    assert body["checks"]["database"] is True
    # Readiness requires Redis too; status code reflects overall state.
    assert r.status_code == (200 if body["ok"] else 503)


def test_request_id_and_security_headers(client):
    r = client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
