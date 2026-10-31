#!/usr/bin/env python3
"""Live contract check: fetch real responses and parse them with the production adapters.

Run ON THE VPS (the build sandbox has no route to these hosts):
    docker compose run --rm api python scripts/check_provider_contracts.py [--save DIR]
or from a checkout:
    cd backend && uv run python ../scripts/check_provider_contracts.py [--save DIR]

Read-only, unauthenticated public endpoints. Exit 1 if any check fails. With --save, raw
responses are written to DIR so they can replace the doc-derived test fixtures.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import timedelta

_root = pathlib.Path(__file__).resolve().parents[1]
# Repo checkout: <root>/backend ; backend container image: /app (scripts copied to /app/scripts)
sys.path.insert(0, str(_root / "backend" if (_root / "backend").is_dir() else _root))

import httpx  # noqa: E402

from app.core.clock import utcnow  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.providers.binance import BinanceProvider  # noqa: E402
from app.providers.boi import BankOfIsraelProvider  # noqa: E402
from app.providers.coinbase import CoinbaseExchangeProvider  # noqa: E402
from app.providers.coingecko import CoinGeckoProvider  # noqa: E402
from app.providers.twelvedata import TwelveDataProvider  # noqa: E402


class Recorder(httpx.HTTPTransport):
    def __init__(self, out: pathlib.Path | None) -> None:
        super().__init__()
        self.out = out

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = super().handle_request(request)
        if self.out:
            resp.read()
            name = request.url.host + request.url.path.replace("/", "_")
            (self.out / f"{name}.txt").write_bytes(resp.content)
        return resp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", type=pathlib.Path)
    args = ap.parse_args()
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
    now = utcnow()
    rec = Recorder(args.save)
    cb = CoinbaseExchangeProvider(transport=rec)
    boi = BankOfIsraelProvider(transport=rec)
    bn = BinanceProvider(transport=rec)
    adapters: list[object] = [cb, boi, bn]
    checks = [
        ("coinbase quote", lambda: cb.get_latest_quote("BTC-USD")),
        (
            "coinbase 1h candles",
            lambda: len(cb.get_intraday_ohlcv("BTC-USD", "1h", now - timedelta(hours=24), now)),
        ),
        ("coinbase order book", lambda: len(cb.get_order_book("BTC-USD", 5).bids)),
        ("coinbase market status", lambda: cb.get_market_status("BTC-USD").status),
        ("coinbase provider status", lambda: cb.get_provider_status().server_time),
        ("boi latest USD", lambda: boi.get_latest_reference_rate("USD")),
        (
            "boi history USD (SDMX XML)",
            lambda: len(
                boi.get_reference_rates("USD", (now - timedelta(days=14)).date(), now.date())
            ),
        ),
        ("binance BTCUSDT book", lambda: binance_quote(bn)),
        (
            "binance BTCUSDT 1m klines",
            lambda: len(bn.get_intraday_ohlcv("BTCUSDT", "1m", now - timedelta(minutes=30), now)),
        ),
    ]
    s = get_settings()
    if s.twelvedata_api_key is not None:
        td = TwelveDataProvider(transport=rec)
        adapters.append(td)
        checks += [
            ("twelvedata plan (/api_usage)", lambda: td.get_plan()),
            ("twelvedata USD/ILS quote", lambda: td.get_latest_quote("USD/ILS")),
            (
                "twelvedata XAU/USD 1h series (timezone=UTC)",
                lambda: len(td.get_intraday_ohlcv("XAU/USD", "1h", now - timedelta(days=3), now)),
            ),
        ]
    else:
        print("SKIP twelvedata: GMI_TWELVEDATA_API_KEY not set")
    if s.coingecko_demo_api_key is not None:
        cg = CoinGeckoProvider(transport=rec)
        adapters.append(cg)
        checks.append(("coingecko bitcoin/usd", lambda: cg.get_latest_quote("bitcoin")))
    else:
        print("SKIP coingecko: GMI_COINGECKO_DEMO_API_KEY not set")
    failed = 0
    for name, fn in checks:
        try:
            print(f"PASS {name}: {fn()}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    for a in adapters:
        a.close()  # type: ignore[attr-defined]
    print(f"\n{len(checks) - failed}/{len(checks)} contract checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


def binance_quote(bn: BinanceProvider) -> object:
    return bn.get_latest_quote("BTCUSDT")
