"""Provider adapter registry."""

from __future__ import annotations

from collections.abc import Callable

from app.providers.base import MarketDataProvider
from app.providers.binance import BinanceProvider
from app.providers.boi import BankOfIsraelProvider
from app.providers.coinbase import CoinbaseExchangeProvider
from app.providers.coingecko import CoinGeckoProvider
from app.providers.twelvedata import TwelveDataProvider

FACTORIES: dict[str, Callable[[], MarketDataProvider]] = {
    "coinbase": CoinbaseExchangeProvider,
    "boi": BankOfIsraelProvider,
    "twelvedata": TwelveDataProvider,
    "coingecko": CoinGeckoProvider,
    "binance": BinanceProvider,
}


def create(name: str) -> MarketDataProvider:
    try:
        return FACTORIES[name]()
    except KeyError:
        raise KeyError(f"no adapter registered for provider '{name}'") from None
