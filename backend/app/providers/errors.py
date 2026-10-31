from __future__ import annotations


class ProviderError(Exception):
    """Base class. Carries the provider name for status bookkeeping."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider


class ProviderUnavailable(ProviderError):
    """Network failure, timeout or 5xx after retries."""


class ProviderRateLimited(ProviderError):
    """HTTP 429 after retries."""


class ProviderRejected(ProviderError):
    """Non-retryable 4xx (bad symbol, forbidden region, ...)."""

    def __init__(self, provider: str, message: str, status_code: int) -> None:
        super().__init__(provider, message)
        self.status_code = status_code


class ProviderDataError(ProviderError):
    """Response did not match the documented contract. Never guessed around."""


class CapabilityNotSupported(ProviderError):
    pass
