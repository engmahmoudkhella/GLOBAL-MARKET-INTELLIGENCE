"""Observed BoI publication times (from PublicApi `lastUpdate`), to decide the fallback.

Report only: the configured fallback (GMI_BOI_PUBLICATION_FALLBACK_TIME) is never changed
automatically. One observation per rate date: the earliest `lastUpdate` seen for that date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import BoiPublicationObservation

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
REQUIRED_BUSINESS_DAYS = 20


def _fmt(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


@dataclass(frozen=True)
class PublicationStats:
    business_days: int
    required: int
    sufficient: bool
    median_local: str | None
    earliest_local: str | None
    latest_local: str | None
    configured_fallback: str
    first_date: str | None
    last_date: str | None


def publication_stats(session: Session, required: int = REQUIRED_BUSINESS_DAYS) -> PublicationStats:
    rows = session.execute(
        select(
            BoiPublicationObservation.rate_date, func.min(BoiPublicationObservation.published_at)
        )
        .group_by(BoiPublicationObservation.rate_date)
        .order_by(BoiPublicationObservation.rate_date)
    ).all()
    secs = []
    for _, published in rows:
        local = published.astimezone(ISRAEL_TZ)
        secs.append(local.hour * 3600 + local.minute * 60 + local.second + local.microsecond / 1e6)
    fallback: time = get_settings().boi_publication_fallback_time
    n = len(secs)
    return PublicationStats(
        business_days=n,
        required=required,
        sufficient=n >= required,
        median_local=_fmt(median(secs)) if secs else None,
        earliest_local=_fmt(min(secs)) if secs else None,
        latest_local=_fmt(max(secs)) if secs else None,
        configured_fallback=fallback.strftime("%H:%M:%S"),
        first_date=rows[0][0].isoformat() if rows else None,
        last_date=rows[-1][0].isoformat() if rows else None,
    )
