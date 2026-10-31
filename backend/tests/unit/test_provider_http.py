import httpx
import pytest

from app.providers.errors import ProviderRateLimited, ProviderRejected, ProviderUnavailable
from app.providers.http import ProviderHttpClient


def client(handler, sleeps, retries=3):
    return ProviderHttpClient(
        "t",
        "https://example.test",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        max_retries=retries,
    )


def test_retries_5xx_with_exponential_backoff_then_succeeds():
    calls, sleeps = [], []

    def h(req):
        calls.append(1)
        return httpx.Response(503 if len(calls) < 3 else 200, json={"ok": True})

    assert client(h, sleeps).get("/x").status_code == 200
    assert len(calls) == 3 and len(sleeps) == 2
    assert 0.25 <= sleeps[0] <= 0.5 and 0.5 <= sleeps[1] <= 1.0  # base 0.5 * 2^n, 50-100% jitter


def test_gives_up_after_max_retries():
    sleeps = []
    with pytest.raises(ProviderUnavailable):
        client(lambda r: httpx.Response(502), sleeps, retries=2).get("/x")
    assert len(sleeps) == 2


def test_429_respects_retry_after_and_raises_rate_limited():
    sleeps = []
    with pytest.raises(ProviderRateLimited):
        client(lambda r: httpx.Response(429, headers={"Retry-After": "7"}), sleeps, 1).get("/x")
    assert sleeps == [7.0]


def test_4xx_not_retried():
    calls, sleeps = [], []

    def h(req):
        calls.append(1)
        return httpx.Response(451)

    with pytest.raises(ProviderRejected) as e:
        client(h, sleeps).get("/x")
    assert e.value.status_code == 451 and len(calls) == 1 and sleeps == []


def test_transport_errors_retried_then_unavailable():
    sleeps = []

    def h(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    with pytest.raises(ProviderUnavailable):
        client(h, sleeps, retries=2).get("/x")
    assert len(sleeps) == 2


def test_sends_user_agent_and_no_auth_headers():
    seen = {}

    def h(req):
        seen.update(req.headers)
        return httpx.Response(200)

    client(h, []).get("/x")
    assert "GMI" in seen["user-agent"]
    assert "authorization" not in seen
