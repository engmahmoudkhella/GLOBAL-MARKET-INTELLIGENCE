#!/usr/bin/env python3
"""Reachability from this host (plan §0.3 gates G6/G7). Run ON THE VPS.

Only unauthenticated GETs on public endpoints; no API keys are sent. Reports HTTP status and
latency. HTTP 451/403 usually means a geographic restriction.
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

TARGETS = [
    ("coinbase (primary BTC-USD)", "https://api.exchange.coinbase.com/time"),
    ("binance api (secondary)", "https://api.binance.com/api/v3/time"),
    ("binance data mirror (secondary)", "https://data-api.binance.vision/api/v3/time"),
    ("coingecko (reference)", "https://api.coingecko.com/api/v3/ping"),
    ("twelvedata (host only)", "https://api.twelvedata.com/"),
    ("bank of israel public api", "https://boi.org.il/PublicApi/GetExchangeRates"),
    (
        "bank of israel sdmx",
        "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/structure/"
        "dataflow/BOI.STATISTICS/EXR/1.0",
    ),
]


def probe(url: str) -> tuple[str, float]:
    if not url.startswith("https://"):
        raise ValueError(url)
    req = urllib.request.Request(  # noqa: S310 - https only, fixed list
        url, headers={"User-Agent": "GMI reachability check"}
    )
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 - fixed https URLs
            return f"HTTP {r.status}", time.monotonic() - t
    except urllib.error.HTTPError as e:
        hint = " (geo-restricted?)" if e.code in (403, 451) else ""
        return f"HTTP {e.code}{hint}", time.monotonic() - t
    except Exception as e:  # noqa: BLE001
        return f"ERROR {type(e).__name__}: {e}", time.monotonic() - t


def main() -> int:
    bad = 0
    for name, url in TARGETS:
        status, secs = probe(url)
        ok = status.startswith("HTTP 2") or (
            name.startswith("twelvedata") and "HTTP 4" in status and "geo" not in status
        )
        bad += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FAIL'} {name:34s} {status:28s} {secs * 1000:7.0f} ms")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
