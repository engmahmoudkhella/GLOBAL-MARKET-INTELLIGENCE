from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone(name: str) -> str:
    """Return `name` if it is a known IANA zone, else raise ValueError."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown IANA timezone: {name!r}") from None
    return name
