"""Bank of Israel representative exchange rates (USD/ILS official reference).

The representative rate is published once per business day. It is a *reference*, not an
executable price: this adapter returns ReferenceRate objects only and offers no quotes.

Endpoints (to be confirmed against live responses on the VPS with
scripts/check_provider_contracts.py - the build sandbox cannot reach boi.org.il):
  * latest:  https://boi.org.il/PublicApi/GetExchangeRates  (JSON)
  * history: https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/
             BOI.STATISTICS/EXR/1.0/RER_<CUR>_ILS?startperiod=...&endperiod=...&format=csv
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.clock import utcnow
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderDataError
from app.providers.http import ProviderHttpClient
from app.providers.models import Capability, ProviderStatus, ReferenceRate
from app.providers.parsing import load_json, require, to_decimal, to_utc

NAME = "boi"
PUBLIC_API = "https://boi.org.il"
SDMX_API = "https://edge.boi.gov.il"
SDMX_PATH = "/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/{series}"
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def series_code(currency_key: str) -> str:
    """'USD' -> 'RER_USD_ILS' (representative exchange rate series)."""
    if not currency_key.isalpha() or len(currency_key) != 3:
        raise ValueError(f"bad currency key {currency_key!r}")
    return f"RER_{currency_key.upper()}_ILS"


class BankOfIsraelProvider(MarketDataProvider):
    name = NAME
    capabilities = frozenset({Capability.REFERENCE_RATE, Capability.PROVIDER_STATUS})

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        kwargs: dict[str, Any] = {"transport": transport, "min_interval": 1.0}
        if sleep is not None:
            kwargs["sleep"] = sleep
        self.public = ProviderHttpClient(NAME, PUBLIC_API, **kwargs)
        self.sdmx = ProviderHttpClient(NAME, SDMX_API, **kwargs)
        self.clock = clock

    def close(self) -> None:
        self.public.close()
        self.sdmx.close()

    def get_latest_reference_rate(self, currency_key: str) -> ReferenceRate:
        resp = self.public.get("/PublicApi/GetExchangeRates")
        received = self.clock()
        data = load_json(NAME, resp.text)
        rates = require(NAME, data, "exchangeRates")
        if not isinstance(rates, list):
            raise ProviderDataError(NAME, "exchangeRates must be a list")
        for item in rates:
            if isinstance(item, dict) and str(item.get("key", "")).upper() == currency_key.upper():
                unit = to_decimal(NAME, require(NAME, item, "unit"), "unit")
                rate = to_decimal(
                    NAME, require(NAME, item, "currentExchangeRate"), "currentExchangeRate"
                )
                published = to_utc(NAME, require(NAME, item, "lastUpdate"), "lastUpdate")
                return ReferenceRate(
                    provider_symbol=currency_key.upper(),
                    rate_date=published.astimezone(ISRAEL_TZ).date(),
                    rate=rate / unit,
                    received_at=received,
                    published_at=published,
                )
        raise ProviderDataError(NAME, f"currency {currency_key!r} not in exchangeRates")

    def get_reference_rates(
        self, provider_symbol: str, start: date, end: date
    ) -> list[ReferenceRate]:
        resp = self.sdmx.get(
            SDMX_PATH.format(series=series_code(provider_symbol)),
            {"startperiod": start.isoformat(), "endperiod": end.isoformat(), "format": "csv"},
        )
        return parse_sdmx_csv(resp.text, provider_symbol.upper(), self.clock())

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        self.public.get("/PublicApi/GetExchangeRates")
        received = self.clock()
        return ProviderStatus(
            ok=True, checked_at=received, latency_ms=int((received - sent).total_seconds() * 1000)
        )


def parse_sdmx_csv(text: str, currency_key: str, received: datetime) -> list[ReferenceRate]:
    """Parse SDMX-CSV by column *name* (TIME_PERIOD, OBS_VALUE); fail on anything else."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if reader.fieldnames is None:
        raise ProviderDataError(NAME, "empty SDMX response")
    cols = {c.strip().upper(): c for c in reader.fieldnames}
    if "TIME_PERIOD" not in cols or "OBS_VALUE" not in cols:
        raise ProviderDataError(NAME, f"SDMX CSV lacks TIME_PERIOD/OBS_VALUE: {reader.fieldnames}")
    series_col = cols.get("SERIES_CODE")
    expected = series_code(currency_key)
    out: dict[date, ReferenceRate] = {}
    for row in reader:
        if series_col and row[series_col].strip() != expected:
            raise ProviderDataError(NAME, f"unexpected series {row[series_col]!r}")
        raw_value = (row[cols["OBS_VALUE"]] or "").strip()
        if raw_value in ("", "NaN"):
            continue  # no observation published for that period; never filled
        try:
            day = date.fromisoformat(row[cols["TIME_PERIOD"]].strip())
        except ValueError as exc:
            raise ProviderDataError(NAME, f"bad TIME_PERIOD {row[cols['TIME_PERIOD']]!r}") from exc
        value: Decimal = to_decimal(NAME, raw_value, "OBS_VALUE")
        if day in out and out[day].rate != value:
            raise ProviderDataError(NAME, f"conflicting values for {day}")
        out[day] = ReferenceRate(currency_key, day, value, received)
    return [out[d] for d in sorted(out)]
