"""Shared HTTP client for providers: timeouts, retries with exponential backoff + jitter,
client-side request pacing. Transport and sleep are injectable for tests."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.providers.errors import (
    ProviderRateLimited,
    ProviderRejected,
    ProviderUnavailable,
)

log = logging.getLogger(__name__)

USER_AGENT = "GMI/0.1 (personal research dashboard; paper trading only)"


class ProviderHttpClient:
    def __init__(
        self,
        provider: str,
        base_url: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_cap: float = 20.0,
        min_interval: float = 0.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.min_interval = min_interval
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_request = 0.0
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
            transport=transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def _pace(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            wait = self._last_request + self.min_interval - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            self._last_request = time.monotonic()

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap)
            except ValueError:
                pass
        delay: float = min(self.backoff_cap, self.backoff_base * (2**attempt))
        return delay * (0.5 + random.random() / 2)  # noqa: S311 - jitter, not crypto

    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._pace()
            try:
                resp = self._client.get(path, params=params)
            except httpx.TransportError as exc:  # includes timeouts
                last_exc = exc
                log.warning("%s transport error on %s: %s", self.provider, path, type(exc).__name__)
                if attempt < self.max_retries:
                    self._sleep(self._backoff(attempt, None))
                    continue
                raise ProviderUnavailable(self.provider, f"{type(exc).__name__} on {path}") from exc
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self.max_retries:
                    self._sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                    continue
                if resp.status_code == 429:
                    raise ProviderRateLimited(self.provider, f"429 on {path}")
                raise ProviderUnavailable(self.provider, f"HTTP {resp.status_code} on {path}")
            if resp.status_code >= 400:
                raise ProviderRejected(
                    self.provider, f"HTTP {resp.status_code} on {path}", resp.status_code
                )
            return resp
        raise ProviderUnavailable(self.provider, f"exhausted retries on {path}") from last_exc
