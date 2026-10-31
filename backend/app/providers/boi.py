"""Bank of Israel representative exchange rates (USD/ILS official reference).

The representative rate is published once per business day (Monday-Friday, observed
2026-10-31) around midday Israel time: the recorded `lastUpdate` was 10:21:03Z = 12:21 IST.
It is a *reference*, not an executable price: this adapter returns ReferenceRate objects only.

Endpoints (verified by the owner 2026-10-31 via browser):
  * latest:  https://www.boi.org.il/PublicApi/GetExchangeRates  (JSON; rates are JSON numbers)
  * history: https://edge.boi.org.il/FusionEdgeServer/sdmx/v2/data/dataflow/
             BOI.STATISTICS/EXR/1.0/RER_<CUR>_ILS?startperiod=...&endperiod=...
             (SDMX-ML 2.1 StructureSpecificData XML; its schemaLocation references
             edge.boi.gov.il, so both domains are checked by the reachability script)
Observation and series attributes (e.g. RELEASE_STATUS="YP") are stored raw, uninterpreted.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.core.clock import utcnow
from app.providers.base import MarketDataProvider
from app.providers.errors import ProviderDataError
from app.providers.http import ProviderHttpClient
from app.providers.models import Capability, ProviderStatus, ReferenceRate
from app.providers.parsing import load_json, require, to_decimal, to_utc

NAME = "boi"
PUBLIC_API = "https://www.boi.org.il"
SDMX_API = "https://edge.boi.org.il"
SDMX_PATH = "/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/{series}"
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def series_code(currency_key: str) -> str:
    """'USD' -> 'RER_USD_ILS' (representative exchange rate series)."""
    if not currency_key.isalpha() or len(currency_key) != 3:
        raise ValueError(f"bad currency key {currency_key!r}")
    return f"RER_{currency_key.upper()}_ILS"


def _json_number(value: Any, field: str, *, positive: bool = True) -> Decimal:
    """BoI JSON sends numbers (parsed from raw text as Decimal, never float); strings are a
    contract change and are rejected."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ProviderDataError(NAME, f"{field}: expected JSON number, got {value!r}")
    return to_decimal(NAME, value, field, positive=positive)


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
        self.sdmx = ProviderHttpClient(
            NAME, SDMX_API, headers={"Accept": "application/xml"}, **kwargs
        )
        self.clock = clock

    def close(self) -> None:
        self.public.close()
        self.sdmx.close()

    def get_latest_reference_rate(self, currency_key: str) -> ReferenceRate:
        resp = self.public.get("/PublicApi/GetExchangeRates")
        received = self.clock()
        return parse_latest_json(resp.text, currency_key, received)

    def get_reference_rates(
        self, provider_symbol: str, start: date, end: date
    ) -> list[ReferenceRate]:
        resp = self.sdmx.get(
            SDMX_PATH.format(series=series_code(provider_symbol)),
            {"startperiod": start.isoformat(), "endperiod": end.isoformat()},
        )
        return parse_sdmx_xml(resp.text, provider_symbol.upper(), self.clock())

    def get_provider_status(self) -> ProviderStatus:
        sent = self.clock()
        self.public.get("/PublicApi/GetExchangeRates")
        received = self.clock()
        return ProviderStatus(
            ok=True, checked_at=received, latency_ms=int((received - sent).total_seconds() * 1000)
        )


def parse_latest_json(text: str, currency_key: str, received: datetime) -> ReferenceRate:
    data = load_json(NAME, text)  # parse_float=Decimal: never via binary float
    rates = require(NAME, data, "exchangeRates")
    if not isinstance(rates, list):
        raise ProviderDataError(NAME, "exchangeRates must be a list")
    for item in rates:
        if isinstance(item, dict) and str(item.get("key", "")).upper() == currency_key.upper():
            unit = require(NAME, item, "unit")
            if isinstance(unit, bool) or not isinstance(unit, int) or unit <= 0:
                raise ProviderDataError(NAME, f"unit must be a positive integer, got {unit!r}")
            rate = _json_number(require(NAME, item, "currentExchangeRate"), "currentExchangeRate")
            change_pct = _json_number(
                require(NAME, item, "currentChange"), "currentChange", positive=False
            )
            published = to_utc(NAME, require(NAME, item, "lastUpdate"), "lastUpdate")
            return ReferenceRate(
                provider_symbol=currency_key.upper(),
                rate_date=published.astimezone(ISRAEL_TZ).date(),
                rate=rate / unit,
                received_at=received,
                published_at=published,
                extra={
                    "source": "PublicApi/GetExchangeRates",
                    "unit": str(unit),
                    "published_rate": format(rate, "f"),
                    "current_change_pct": format(change_pct, "f"),
                },
            )
    raise ProviderDataError(NAME, f"currency {currency_key!r} not in exchangeRates")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sdmx_xml(text: str, currency_key: str, received: datetime) -> list[ReferenceRate]:
    """Parse SDMX-ML 2.1 StructureSpecificData. Namespace-agnostic; external entities and
    entity expansion are refused (defusedxml)."""
    try:
        root = ElementTree.fromstring(text.encode())
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise ProviderDataError(NAME, f"invalid SDMX XML: {exc}") from exc
    if _local(root.tag) != "StructureSpecificData":
        raise ProviderDataError(NAME, f"unexpected SDMX root {_local(root.tag)!r}")
    expected = series_code(currency_key)
    out: dict[date, ReferenceRate] = {}
    for series in (e for e in root.iter() if _local(e.tag) == "Series"):
        attrs = dict(series.attrib)
        if attrs.get("SERIES_CODE") != expected:
            raise ProviderDataError(NAME, f"unexpected series {attrs.get('SERIES_CODE')!r}")
        if attrs.get("UNIT_MULT", "0") != "0":
            raise ProviderDataError(NAME, f"unsupported UNIT_MULT {attrs.get('UNIT_MULT')!r}")
        for obs in (e for e in series if _local(e.tag) == "Obs"):
            o = dict(obs.attrib)
            raw_value = (o.get("OBS_VALUE") or "").strip()
            if raw_value in ("", "NaN"):
                continue  # nothing published for that period; never filled
            try:
                day = date.fromisoformat(o.get("TIME_PERIOD", ""))
            except ValueError as exc:
                raise ProviderDataError(NAME, f"bad TIME_PERIOD {o.get('TIME_PERIOD')!r}") from exc
            value = to_decimal(NAME, raw_value, "OBS_VALUE")
            if day in out and out[day].rate != value:
                raise ProviderDataError(NAME, f"conflicting values for {day}")
            extra = {
                "source": "SDMX EXR",
                **{f"series.{k}": v for k, v in attrs.items()},
                **{f"obs.{k}": v for k, v in o.items() if k not in ("TIME_PERIOD", "OBS_VALUE")},
            }
            out[day] = ReferenceRate(currency_key, day, value, received, extra=extra)
    return [out[d] for d in sorted(out)]
