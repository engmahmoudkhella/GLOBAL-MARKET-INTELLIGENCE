"""CoinGecko Demo API: independent BTC/USD *reference* price (never the primary BTCUSD source).

Doc-derived contract (UNVERIFIED live - record from the VPS):
  GET https://api.coingecko.com/api/v3/simple/price
      ?ids=bitcoin&vs_currencies=usd&include_last_updated_at=true&precision=full
  -> {"bitcoin": {"usd": <number>, "last_updated_at": <epoch s>}}
  GET /api/v3/ping -> {"gecko_says": "..."}
Key sent in the `x-cg-demo-api-key` header. Demo plan: 30 calls/min, 10,000 calls/month,
attribution required ("Powered by CoinGecko API").
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.clock import utcnow
from app.core.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderDataError, ProviderRejected
from app.providers.http import ProviderHttpClient
from app.providers.models import Capability, ProviderStatus, Quote
from app.providers.parsing import epoch_seconds, load_json, note_unknown_fields, require, to_decimal

NAME = "coingecko"
BASE_URL = "https://api.coingecko.com"
ATTRIBUTION = "Powered by CoinGecko API"
COIN_FIELDS = frozenset({"usd", "last_updated_at"})


class CoinGeckoProvider(MarketDataProvider):
    name = NAME
    capabilities = frozenset({Capability.LATEST_QUOTE, Capability.PROVIDER_STATUS})

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        if api_key is None:
            secret = get_settings().coingecko_demo_api_key
            if secret is None:
                raise ProviderRejected(NAME, "GMI_COINGECKO_DEMO_API_KEY is not configured", 401)
            api_key = secret.get_secret_value()
        kwargs: dict[str, Any] = {
            "transport": transport,
            "min_interval": 2.5,
            "headers": {"x-cg-demo-api-key": api_key},
        }
        if sleep is not None:
            kwargs["sleep"] = sleep
        self.http = ProviderHttpClient(NAME, BASE_URL, **kwargs)
        self.clock = clock

    def close(self) -> None:
        self.http.close()

    def get_latest_quote(self, provider_symbol: str) -> Quote:
        resp = self.http.get(
            "/api/v3/simple/price",
            {
                "ids": provider_symbol,
                "vs_currencies": "usd",
                "include_last_updated_at": "true",
                "precision": "full",
            },
        )
        received = self.clock()
        data = load_json(NAME, resp.text)
        coin = require(NAME, data, provider_symbol)
        note_unknown_fields(NAME, "simple/price", coin, COIN_FIELDS)
        usd = require(NAME, coin, "usd")
        if isinstance(usd, bool) or not isinstance(usd, (Decimal, int)):
            raise ProviderDataError(NAME, f"usd: expected JSON number, got {usd!r}")
        return Quote(
            provider_symbol=provider_symbol,
            observed_at=epoch_seconds(
                NAME, require(NAME, coin, "last_updated_at"), "last_updated_at"
            ),
            received_at=received,
            last_price=to_decimal(NAME, usd, "usd"),
        )

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        resp = self.http.get("/api/v3/ping")
        received = self.clock()
        require(NAME, load_json(NAME, resp.text), "gecko_says")
        return ProviderStatus(
            ok=True, checked_at=received, latency_ms=int((received - sent).total_seconds() * 1000)
        )
