"""Coinbase Exchange public market data (BTC-USD primary source, plan §0.2).

Public, unauthenticated endpoints only. This module must never call order, account or
withdrawal endpoints (enforced by scripts/check_no_real_trading.py).
Base URL: https://api.exchange.coinbase.com   Docs: docs.cdp.coinbase.com/exchange
Documented public limit: ~10 req/s per IP; we pace at <= 4 req/s.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    MarketState,
    MarketStatus,
    OrderBook,
    OrderBookLevel,
    ProviderStatus,
    Quote,
    Timeframe,
)
from app.providers.parsing import (
    load_json,
    note_unknown_fields,
    require,
    to_decimal,
    to_decimal_str,
    to_utc,
)

TICKER_FIELDS = frozenset({"ask", "bid", "volume", "trade_id", "price", "size", "time"})

NAME = "coinbase"
BASE_URL = "https://api.exchange.coinbase.com"
MAX_CANDLES_PER_REQUEST = 300
# Coinbase Exchange supports these granularities only (seconds). No 4h.
GRANULARITY: dict[str, int] = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


class CoinbaseExchangeProvider(MarketDataProvider):
    name = NAME
    capabilities = frozenset(
        {
            Capability.LATEST_QUOTE,
            Capability.HISTORICAL_OHLCV,
            Capability.INTRADAY_OHLCV,
            Capability.ORDER_BOOK,
            Capability.MARKET_STATUS,
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

    def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, datetime]:
        resp = self.http.get(path, params=params)
        return load_json(NAME, resp.text), self.clock()

    def get_latest_quote(self, provider_symbol: str) -> Quote:
        data, received = self._get(f"/products/{provider_symbol}/ticker")
        # Recorded 2026-10-31: bid/ask/price are strings; `time` has 6 or 9 fractional digits.
        # `time` is the last trade time; bid/ask are the book at response time.
        note_unknown_fields(NAME, "ticker", data, TICKER_FIELDS)
        return Quote(
            provider_symbol=provider_symbol,
            observed_at=to_utc(NAME, require(NAME, data, "time"), "time"),
            received_at=received,
            bid=to_decimal_str(NAME, require(NAME, data, "bid"), "bid"),
            ask=to_decimal_str(NAME, require(NAME, data, "ask"), "ask"),
            last_price=to_decimal_str(NAME, require(NAME, data, "price"), "price"),
        )

    def _candles(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        if timeframe not in GRANULARITY:
            raise CapabilityNotSupported(
                NAME, f"timeframe {timeframe} not offered by Coinbase (derive from 1h)"
            )
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        gran = GRANULARITY[timeframe]
        step = timedelta(seconds=gran * MAX_CANDLES_PER_REQUEST)
        out: dict[datetime, Candle] = {}
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + step)
            data, received = self._get(
                f"/products/{provider_symbol}/candles",
                {"granularity": gran, "start": cursor.isoformat(), "end": chunk_end.isoformat()},
            )
            if not isinstance(data, list):
                raise ProviderDataError(NAME, "candles: expected a JSON array")
            for row in data:
                c = self._parse_candle(provider_symbol, timeframe, row, received)
                if start <= c.open_time < end:
                    out[c.open_time] = c
            cursor = chunk_end
        return [out[k] for k in sorted(out)]

    def _parse_candle(
        self, symbol: str, timeframe: Timeframe, row: Any, received: datetime
    ) -> Candle:
        # Recorded 2026-10-31: [time, LOW, HIGH, OPEN, CLOSE, volume], JSON numbers, newest
        # first. Columns are mapped explicitly by position and the order is asserted.
        if not isinstance(row, list) or len(row) != 6:
            raise ProviderDataError(NAME, f"candle row must have 6 fields, got {row!r}")
        ts = row[0]
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise ProviderDataError(NAME, f"candle time must be integer epoch seconds: {ts!r}")
        for i, v in enumerate(row[1:], start=1):
            if isinstance(v, (bool, str)) or not isinstance(v, (int, Decimal)):
                raise ProviderDataError(NAME, f"candle column {i} must be a JSON number: {v!r}")
        low = to_decimal(NAME, row[1], "low")
        high = to_decimal(NAME, row[2], "high")
        open_ = to_decimal(NAME, row[3], "open")
        close = to_decimal(NAME, row[4], "close")
        volume = to_decimal(NAME, row[5], "volume", positive=False)
        if not (low <= min(open_, close) and max(open_, close) <= high):
            raise ProviderDataError(
                NAME, f"candle {ts}: expected low <= open,close <= high (column order changed?)"
            )
        open_time = datetime.fromtimestamp(ts, UTC)
        return Candle(
            provider_symbol=symbol,
            timeframe=timeframe,
            open_time=open_time,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            received_at=received,
            is_complete=open_time + TIMEFRAME_DELTA[timeframe] <= received,
        )

    def get_intraday_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._candles(provider_symbol, timeframe, start, end)

    def get_historical_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._candles(provider_symbol, timeframe, start, end)

    def get_order_book(self, provider_symbol: str, depth: int = 50) -> OrderBook:
        data, received = self._get(f"/products/{provider_symbol}/book", {"level": 2})

        def levels(side: str) -> tuple[OrderBookLevel, ...]:
            raw = require(NAME, data, side)
            if not isinstance(raw, list):
                raise ProviderDataError(NAME, f"book.{side} must be a list")
            out = []
            for lvl in raw[:depth]:
                if not isinstance(lvl, list) or len(lvl) < 2:
                    raise ProviderDataError(NAME, f"bad book level {lvl!r}")
                out.append(
                    OrderBookLevel(
                        to_decimal(NAME, lvl[0], "price"), to_decimal(NAME, lvl[1], "size")
                    )
                )
            return tuple(out)

        observed = (
            to_utc(NAME, data["time"], "time")
            if isinstance(data, dict) and data.get("time")
            else None
        )
        return OrderBook(provider_symbol, observed, received, levels("bids"), levels("asks"))

    def get_market_status(self, provider_symbol: str) -> MarketStatus:
        data, received = self._get(f"/products/{provider_symbol}")
        status = require(NAME, data, "status")
        disabled = bool(data.get("trading_disabled")) or bool(data.get("cancel_only"))
        state: MarketState
        if status == "online" and not disabled:
            state = "open"
        elif status in ("delisted", "offline") or disabled:
            state = "halted"
        else:
            state = "unknown"
        return MarketStatus(provider_symbol, state, data.get("status_message") or status, received)

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        data, received = self._get("/time")
        server = to_utc(NAME, require(NAME, data, "iso"), "iso")
        return ProviderStatus(
            ok=True,
            checked_at=received,
            latency_ms=int((received - sent).total_seconds() * 1000),
            server_time=server,
        )
