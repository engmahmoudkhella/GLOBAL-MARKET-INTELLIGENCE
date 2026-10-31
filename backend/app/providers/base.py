"""Provider interface (SRS §5.1). Analytical code depends only on this, never on a vendor.

Adapters declare `capabilities`; calling an undeclared method raises CapabilityNotSupported.
"""

from __future__ import annotations

from datetime import date, datetime

from app.providers.errors import CapabilityNotSupported
from app.providers.models import (
    Candle,
    Capability,
    MarketStatus,
    OrderBook,
    ProviderStatus,
    Quote,
    ReferenceRate,
    Timeframe,
)


class MarketDataProvider:
    name: str = "base"
    capabilities: frozenset[Capability] = frozenset()

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def _unsupported(self, capability: Capability) -> CapabilityNotSupported:
        return CapabilityNotSupported(self.name, f"capability '{capability}' not supported")

    # Required interface (SRS §5.1); not every provider implements every method.
    def get_latest_quote(self, provider_symbol: str) -> Quote:
        raise self._unsupported(Capability.LATEST_QUOTE)

    def get_historical_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        raise self._unsupported(Capability.HISTORICAL_OHLCV)

    def get_intraday_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        raise self._unsupported(Capability.INTRADAY_OHLCV)

    def get_order_book(self, provider_symbol: str, depth: int = 50) -> OrderBook:
        raise self._unsupported(Capability.ORDER_BOOK)

    def get_market_status(self, provider_symbol: str) -> MarketStatus:
        raise self._unsupported(Capability.MARKET_STATUS)

    def get_provider_status(self) -> ProviderStatus:
        raise self._unsupported(Capability.PROVIDER_STATUS)

    # Official reference publications (not market quotes).
    def get_reference_rates(
        self, provider_symbol: str, start: date, end: date
    ) -> list[ReferenceRate]:
        raise self._unsupported(Capability.REFERENCE_RATE)

    def close(self) -> None:  # pragma: no cover - adapters override when they hold clients
        return None
