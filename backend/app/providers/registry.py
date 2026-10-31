"""Provider adapter registry. Twelve Data is intentionally absent until coverage is confirmed
(plan §0.2a)."""

from __future__ import annotations

from collections.abc import Callable

from app.providers.base import MarketDataProvider
from app.providers.boi import BankOfIsraelProvider
from app.providers.coinbase import CoinbaseExchangeProvider

FACTORIES: dict[str, Callable[[], MarketDataProvider]] = {
    "coinbase": CoinbaseExchangeProvider,
    "boi": BankOfIsraelProvider,
}


def create(name: str) -> MarketDataProvider:
    try:
        return FACTORIES[name]()
    except KeyError:
        raise KeyError(f"no adapter registered for provider '{name}'") from None
