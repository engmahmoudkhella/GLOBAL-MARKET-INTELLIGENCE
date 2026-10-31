"""Twelve Data adapter: USD/ILS and XAU/USD (plan §0.2a).

Contract notes (from the owner's recorded /quote responses, 2026-10-31, free Basic key):
  * all numeric fields are JSON strings -> parsed strictly to Decimal, anything else rejected;
  * /quote has no bid/ask on this plan -> last price only (price_type "last");
  * `last_quote_at` (epoch s) is the observation time; `timestamp` is the provider's *daily bar*
    start (16:00 New York), which we do not use;
  * `is_market_open` is NOT trusted (it reported true on a Saturday). It is kept in
    provider_flags for audit; our session calendar decides.
Provider daily bars are never stored: daily/4h candles are derived from our own intraday data
(app/ingestion/aggregate.py). Authentication uses the `Authorization: apikey` header so the key
never appears in a URL or log line.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.clock import utcnow
from app.core.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.errors import (
    CapabilityNotSupported,
    ProviderDataError,
    ProviderRateLimited,
    ProviderRejected,
)
from app.providers.http import ProviderHttpClient
from app.providers.models import (
    TIMEFRAME_DELTA,
    Candle,
    Capability,
    ProviderStatus,
    Quote,
    Timeframe,
)
from app.providers.parsing import epoch_seconds, load_json, require, to_decimal_str

NAME = "twelvedata"
FUTURE_TOLERANCE = timedelta(minutes=1)
BASE_URL = "https://api.twelvedata.com"
MAX_OUTPUTSIZE = 5000
# Intraday only. 4h and 1d are derived locally from 1h with documented boundaries.
INTERVALS: dict[str, str] = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h"}


class TwelveDataProvider(MarketDataProvider):
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
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        if api_key is None:
            secret = get_settings().twelvedata_api_key
            if secret is None:
                raise ProviderRejected(NAME, "GMI_TWELVEDATA_API_KEY is not configured", 401)
            api_key = secret.get_secret_value()
        kwargs: dict[str, Any] = {
            "transport": transport,
            "min_interval": 0.5,
            "headers": {"Authorization": f"apikey {api_key}"},
        }
        if sleep is not None:
            kwargs["sleep"] = sleep
        self.http = ProviderHttpClient(NAME, BASE_URL, **kwargs)
        self.clock = clock

    def close(self) -> None:
        self.http.close()

    def _get(self, path: str, params: dict[str, Any]) -> tuple[Any, datetime]:
        resp = self.http.get(path, params=params)
        received = self.clock()
        data = load_json(NAME, resp.text)
        if isinstance(data, dict) and data.get("status") == "error":
            code = data.get("code")
            msg = str(data.get("message", "error"))[:300]
            if code == 429:
                raise ProviderRateLimited(NAME, f"credits exhausted: {msg}")
            raise ProviderRejected(
                NAME, f"code {code}: {msg}", code if isinstance(code, int) else 400
            )
        return data, received

    def get_latest_quote(self, provider_symbol: str) -> Quote:
        data, received = self._get("/quote", {"symbol": provider_symbol})
        if require(NAME, data, "symbol") != provider_symbol:
            raise ProviderDataError(NAME, f"asked {provider_symbol}, got {data['symbol']!r}")
        bid = to_decimal_str(NAME, data["bid"], "bid") if "bid" in data else None
        ask = to_decimal_str(NAME, data["ask"], "ask") if "ask" in data else None
        flags = {}
        if "is_market_open" in data:
            flags["is_market_open"] = str(data["is_market_open"]).lower()
        return Quote(
            provider_symbol=provider_symbol,
            observed_at=epoch_seconds(NAME, require(NAME, data, "last_quote_at"), "last_quote_at"),
            received_at=received,
            bid=bid,
            ask=ask,
            last_price=to_decimal_str(NAME, require(NAME, data, "close"), "close"),
            provider_flags=flags,
        )

    def _series(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        if timeframe not in INTERVALS:
            raise CapabilityNotSupported(
                NAME, f"{timeframe} bars are not taken from Twelve Data (derived locally)"
            )
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        step = TIMEFRAME_DELTA[timeframe] * MAX_OUTPUTSIZE
        out: dict[datetime, Candle] = {}
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + step)
            data, received = self._get(
                "/time_series",
                {
                    "symbol": provider_symbol,
                    "interval": INTERVALS[timeframe],
                    "timezone": "UTC",
                    "start_date": cursor.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "end_date": chunk_end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "order": "asc",
                    "outputsize": MAX_OUTPUTSIZE,
                },
            )
            meta = require(NAME, data, "meta")
            # Recorded 2026-10-31: meta has NO timezone field, and without timezone=UTC the
            # datetimes are not UTC. We always send timezone=UTC; a timezone field, if present,
            # must say UTC, and no bar may start in the future (checked below).
            if "exchange_timezone" in meta and meta["exchange_timezone"] != "UTC":
                raise ProviderDataError(
                    NAME, f"expected UTC series, got {meta['exchange_timezone']}"
                )
            if require(NAME, meta, "interval") != INTERVALS[timeframe]:
                raise ProviderDataError(NAME, f"interval mismatch {meta['interval']!r}")
            values = require(NAME, data, "values")
            if not isinstance(values, list):
                raise ProviderDataError(NAME, "values must be a list")
            parsed = [self._candle(provider_symbol, timeframe, v, received) for v in values]
            future = [c.open_time for c in parsed if c.open_time > received + FUTURE_TOLERANCE]
            if future:
                raise ProviderDataError(
                    NAME,
                    f"bar(s) start in the future ({max(future).isoformat()} > received "
                    f"{received.isoformat()}): datetimes are not UTC; response rejected",
                )
            for c in parsed:
                if start <= c.open_time < end:
                    out[c.open_time] = c
            cursor = chunk_end
        return [out[k] for k in sorted(out)]

    def _candle(self, symbol: str, tf: Timeframe, v: Any, received: datetime) -> Candle:
        raw = require(NAME, v, "datetime")
        try:
            open_time = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except (TypeError, ValueError) as exc:
            raise ProviderDataError(NAME, f"bad datetime {raw!r}") from exc
        volume = (
            to_decimal_str(NAME, v["volume"], "volume", positive=False) if "volume" in v else None
        )
        return Candle(
            provider_symbol=symbol,
            timeframe=tf,
            open_time=open_time,
            open=to_decimal_str(NAME, require(NAME, v, "open"), "open"),
            high=to_decimal_str(NAME, require(NAME, v, "high"), "high"),
            low=to_decimal_str(NAME, require(NAME, v, "low"), "low"),
            close=to_decimal_str(NAME, require(NAME, v, "close"), "close"),
            volume=volume,
            received_at=received,
            is_complete=open_time + TIMEFRAME_DELTA[tf] <= received,
        )

    def get_intraday_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._series(provider_symbol, timeframe, start, end)

    def get_historical_ohlcv(
        self, provider_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._series(provider_symbol, timeframe, start, end)

    def get_plan(self) -> TwelveDataPlan:
        """Actual plan limits from /api_usage (recorded 2026-10-31: basic, 8/min, 800/day)."""
        data, _ = self._get("/api_usage", {})
        return parse_plan(data)

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        data, received = self._get("/api_usage", {})
        plan = parse_plan(data)
        return ProviderStatus(
            ok=True,
            checked_at=received,
            latency_ms=int((received - sent) / timedelta(milliseconds=1)),
            detail=f"plan {plan.category}: {plan.current_usage}/{plan.per_minute} credits this "
            f"minute, {plan.daily_usage}/{plan.per_day or 'unlimited'} today",
        )


@dataclass(frozen=True)
class TwelveDataPlan:
    category: str
    per_minute: int
    per_day: int  # 0 = no daily limit reported
    current_usage: int
    daily_usage: int | None


def _int_field(data: Any, key: str, *, required: bool = True) -> int | None:
    if not required and (not isinstance(data, dict) or key not in data):
        return None
    v = require(NAME, data, key)
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ProviderDataError(NAME, f"{key}: expected non-negative integer, got {v!r}")
    return v


def parse_plan(data: Any) -> TwelveDataPlan:
    per_minute = _int_field(data, "plan_limit")
    current = _int_field(data, "current_usage")
    assert per_minute is not None and current is not None
    per_day = _int_field(data, "plan_daily_limit", required=False)
    category = data.get("plan_category") if isinstance(data, dict) else None
    return TwelveDataPlan(
        category=str(category) if category is not None else "unknown",
        per_minute=per_minute,
        per_day=per_day or 0,
        current_usage=current,
        daily_usage=_int_field(data, "daily_usage", required=False),
    )
