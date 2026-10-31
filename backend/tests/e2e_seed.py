"""E2E DEVELOPMENT FIXTURE SEED - only for the throwaway Playwright database.

Ingests the owner's recorded Twelve Data USD/ILS /quote response (Saturday 2026-10-31) through
the real adapter + ingestion pipeline, so the UI can be tested showing an out-of-session quote
as excluded. Refuses to run unless GMI_E2E_SEED=1 and the database name contains 'e2e'.
"""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import UTC, datetime

import httpx
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.ingestion import service
from app.providers.twelvedata import TwelveDataProvider

FIXTURE = (
    pathlib.Path(__file__).parent
    / "fixtures"
    / "providers"
    / "twelvedata_quote_usdils.recorded-2026-10-31.json"
)


def main() -> int:
    db_name = make_url(get_settings().database_url).database or ""
    if os.environ.get("GMI_E2E_SEED") != "1" or "e2e" not in db_name:
        print("refusing: set GMI_E2E_SEED=1 and use a database whose name contains 'e2e'")
        return 2
    text = FIXTURE.read_text()
    adapter = TwelveDataProvider(
        api_key="e2e-fixture",
        sleep=lambda s: None,
        clock=lambda: datetime(2026, 10, 31, 10, 27, 30, tzinfo=UTC),
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=text)),
    )
    with get_sessionmaker()() as session:
        r = service.ingest_quote(session, "USDILS", adapter)
    print(f"seeded USDILS recorded quote: {r}")
    return 0 if r.ok and r.statuses == {"suspect": 1} else 1


if __name__ == "__main__":
    sys.exit(main())
