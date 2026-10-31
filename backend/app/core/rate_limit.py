"""Fixed-window rate limiting per client IP (SRS §19).

Backends: Redis (production) and in-memory (tests / single process). If Redis is
unreachable the limiter fails *open* and logs an error, so a Redis outage does not
lock the owner out; the outage is visible in /health/ready.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimited

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int


class RateLimitBackend(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> Decision: ...


class MemoryBackend:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, int]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> Decision:
        now = int(self._clock())
        window = now // window_seconds
        with self._lock:
            w, count = self._counts.get(key, (window, 0))
            if w != window:
                w, count = window, 0
            count += 1
            self._counts[key] = (w, count)
        retry = window_seconds - (now % window_seconds)
        return Decision(count <= limit, retry)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


class RedisBackend:
    def __init__(self, url: str) -> None:
        import redis

        self._redis = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)

    def hit(self, key: str, limit: int, window_seconds: int) -> Decision:
        now = int(time.time())
        window = now // window_seconds
        rkey = f"rl:{key}:{window}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(rkey)
            pipe.expire(rkey, window_seconds + 1)
            count = int(pipe.execute()[0])
        except Exception:  # noqa: BLE001 - fail open, see module docstring
            log.error("rate limiter backend unavailable; failing open")
            return Decision(True, 0)
        return Decision(count <= limit, window_seconds - (now % window_seconds))


@lru_cache
def get_backend() -> RateLimitBackend:
    s = get_settings()
    if s.rate_limit_backend == "memory":
        return MemoryBackend()
    return RedisBackend(s.redis_url)


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


def limit(scope: str, per_minute: Callable[[], int]) -> Callable[[Request], None]:
    """Build a FastAPI dependency enforcing `per_minute` requests per IP for `scope`."""

    def _dep(request: Request) -> None:
        decision = get_backend().hit(f"{scope}:{client_ip(request)}", per_minute(), 60)
        if not decision.allowed:
            raise RateLimited("Rate limit exceeded", retry_after=decision.retry_after)

    return _dep


default_limit = limit("default", lambda: get_settings().rate_limit_default_per_minute)
login_limit = limit("login", lambda: get_settings().rate_limit_login_per_minute)
