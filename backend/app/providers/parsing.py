"""Strict parsing helpers. Any deviation from the documented contract raises ProviderDataError."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.providers.errors import ProviderDataError


def load_json(provider: str, text: str) -> Any:
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise ProviderDataError(provider, f"invalid JSON: {exc.msg}") from exc


def to_decimal(provider: str, value: Any, field: str, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ProviderDataError(provider, f"{field}: expected number, got {value!r}")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProviderDataError(provider, f"{field}: not a number: {value!r}") from exc
    if not d.is_finite():
        raise ProviderDataError(provider, f"{field}: non-finite value")
    if positive and d <= 0:
        raise ProviderDataError(provider, f"{field}: must be > 0, got {d}")
    return d


def to_utc(provider: str, value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ProviderDataError(provider, f"{field}: expected ISO timestamp, got {value!r}")
    v = value.strip().replace("Z", "+00:00")
    # Python's fromisoformat accepts up to 6 fractional digits; some APIs send 7.
    if "." in v:
        head, _, rest = v.partition(".")
        frac = ""
        i = 0
        while i < len(rest) and rest[i].isdigit():
            frac += rest[i]
            i += 1
        v = f"{head}.{frac[:6]}{rest[i:]}" if frac else head + rest[i:]
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as exc:
        raise ProviderDataError(provider, f"{field}: bad timestamp {value!r}") from exc
    if dt.tzinfo is None:
        raise ProviderDataError(provider, f"{field}: timestamp without timezone {value!r}")
    return dt.astimezone(UTC)


def require(provider: str, obj: Any, key: str) -> Any:
    if not isinstance(obj, dict) or key not in obj:
        raise ProviderDataError(provider, f"missing field '{key}'")
    return obj[key]


def to_decimal_str(provider: str, value: Any, field: str, *, positive: bool = True) -> Decimal:
    """Strict variant for providers whose contract sends numbers as JSON strings."""
    if not isinstance(value, str):
        raise ProviderDataError(provider, f"{field}: expected numeric string, got {value!r}")
    return to_decimal(provider, value.strip(), field, positive=positive)


def epoch_seconds(provider: str, value: Any, field: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProviderDataError(
            provider, f"{field}: expected positive integer epoch, got {value!r}"
        )
    return datetime.fromtimestamp(value, UTC)
