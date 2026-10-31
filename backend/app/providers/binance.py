"""Binance public market data: BTCUSDT *secondary* series (USDT-quoted, never relabelled USD).

Uses the market-data-only host data-api.binance.vision (Binance restricted EU services in
July 2026; api.binance.com answers HTTP 451 in blocked regions). Doc-derived contract
(UNVERIFIED live - record from the VPS):
  GET /api/v3/ticker/bookTicker?symbol=BTCUSDT
      -> {"symbol","bidPrice","bidQty","askPrice","askQty"} (strings, NO timestamp)
  GET /api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=ms&endTime=ms&limit=1000
      -> [[openTime ms, "open","high","low","close","volume", closeTime ms, ...], ...]
  GET /api/v3/time -> {"serverTime": ms}
bookTicker has no timestamp, so observed_at = our reception time and the quote carries
provider_flags {"observed_at_source": "received"}.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.clock import utcnow
from app.providers.base import MarketDataProvider
from app.providers.errors import CapabilityNotSupported, ProviderDataError
from app.providers.http import ProviderHttpClient
from app.providers.models import (
    TIMEFRAME_DELTA,
    Candle,
    Capability,
    ProviderStatus,
    Quote,
    Timeframe,
)
from app.providers.parsing import load_json, note_unknown_fields, require, to_decimal_str

NAME = "binance"
BASE_URL = "https://data-api.binance.vision"
MAX_LIMIT = 1000
INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h"}
BOOK_FIELDS = frozenset({"symbol", "bidPrice", "bidQty", "askPrice", "askQty"})


def _ms(provider: str, v: Any, field: str) -> datetime:
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ProviderDataError(provider, f"{field}: expected epoch milliseconds, got {v!r}")
    return datetime.fromtimestamp(v / 1000, UTC)


class BinanceProvider(MarketDataProvider):
    name = NAME
    capabilities = frozenset(
        {
            Capability.LATEST_QUOTE,
            Capability.INTRADAY_OHLCV,
            Capability.HISTORICAL_OHLCV,
            Capability.PROVIDER_STATUS,
        }
    )

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] = utcnow,
        base_url: str = BASE_URL,
    ) -> None:
        kwargs: dict[str, Any] = {"transport": transport, "min_interval": 0.25}
        if sleep is not None:
            kwargs["sleep"] = sleep
        self.http = ProviderHttpClient(NAME, base_url, **kwargs)
        self.clock = clock

    def close(self) -> None:
        self.http.close()

    def get_latest_quote(self, provider_symbol: str) -> Quote:
        resp = self.http.get("/api/v3/ticker/bookTicker", {"symbol": provider_symbol})
        received = self.clock()
        data = load_json(NAME, resp.text)
        note_unknown_fields(NAME, "bookTicker", data, BOOK_FIELDS)
        if require(NAME, data, "symbol") != provider_symbol:
            raise ProviderDataError(NAME, f"asked {provider_symbol}, got {data['symbol']!r}")
        return Quote(
            provider_symbol=provider_symbol,
            observed_at=received,
            received_at=received,
            bid=to_decimal_str(NAME, require(NAME, data, "bidPrice"), "bidPrice"),
            ask=to_decimal_str(NAME, require(NAME, data, "askPrice"), "askPrice"),
            provider_flags={"observed_at_source": "received"},
        )

    def _klines(self, symbol: str, tf: Timeframe, start: datetime, end: datetime) -> list[Candle]:
        if tf not in INTERVALS:
            raise CapabilityNotSupported(NAME, f"{tf} bars are derived locally")
        step = TIMEFRAME_DELTA[tf] * MAX_LIMIT
        out: dict[datetime, Candle] = {}
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + step)
            resp = self.http.get(
                "/api/v3/klines",
                {
                    "symbol": symbol,
                    "interval": INTERVALS[tf],
                    "limit": MAX_LIMIT,
                    "startTime": int(cursor.timestamp() * 1000),
                    "endTime": int(chunk_end.timestamp() * 1000) - 1,
                },
            )
            received = self.clock()
            rows = load_json(NAME, resp.text)
            if not isinstance(rows, list):
                raise ProviderDataError(NAME, "klines: expected a JSON array")
            for row in rows:
                c = self._kline(symbol, tf, row, received)
                if start <= c.open_time < end:
                    out[c.open_time] = c
            cursor = chunk_end
        return [out[k] for k in sorted(out)]

    def _kline(self, symbol: str, tf: Timeframe, row: Any, received: datetime) -> Candle:
        if not isinstance(row, list) or len(row) < 7:
            raise ProviderDataError(NAME, f"kline row must have >= 7 fields, got {row!r}")
        open_time = _ms(NAME, row[0], "openTime")
        close_time = _ms(NAME, row[6], "closeTime")
        # closeTime is the last millisecond of the bar
        if close_time + timedelta(milliseconds=1) != open_time + TIMEFRAME_DELTA[tf]:
            raise ProviderDataError(NAME, f"kline {row[0]}: closeTime does not match {tf}")
        o = to_decimal_str(NAME, row[1], "open")
        h = to_decimal_str(NAME, row[2], "high")
        lo = to_decimal_str(NAME, row[3], "low")
        c = to_decimal_str(NAME, row[4], "close")
        if not (lo <= min(o, c) and max(o, c) <= h):
            raise ProviderDataError(NAME, f"kline {row[0]}: low <= open,close <= high violated")
        return Candle(
            symbol,
            tf,
            open_time,
            o,
            h,
            lo,
            c,
            to_decimal_str(NAME, row[5], "volume", positive=False),
            received,
            is_complete=open_time + TIMEFRAME_DELTA[tf] <= received,
        )

    def get_intraday_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._klines(provider_symbol, timeframe, start, end)

    def get_historical_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._klines(provider_symbol, timeframe, start, end)

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        resp = self.http.get("/api/v3/time")
        received = self.clock()
        server = _ms(NAME, require(NAME, load_json(NAME, resp.text), "serverTime"), "serverTime")
        return ProviderStatus(
            ok=True,
            checked_at=received,
            server_time=server,
            latency_ms=int((received - sent).total_seconds() * 1000),
        )
