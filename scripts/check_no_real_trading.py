#!/usr/bin/env python3
"""Guard: GMI v1 must contain no real-money execution code (SRS §19.1).

Scans source files for exchange/broker order, withdrawal and trading-credential patterns.
Exit code 1 if anything is found. Run in CI and in the backend test suite.
"""

from __future__ import annotations

import pathlib
import re
import sys

CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".yml", ".yaml",
                 ".toml", ".json", ".env", ".example", ".sh", ".conf"}
SKIP_DIRS = {".git", "node_modules", ".next", ".venv", "__pycache__", ".mypy_cache",
             ".ruff_cache", ".pytest_cache", "docs"}
# Files that must mention the patterns in order to test or define the guard.
ALLOWLIST = {"scripts/check_no_real_trading.py",
             "backend/tests/unit/test_no_real_trading_guard.py"}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("binance order endpoint", re.compile(r"/(api/v3|fapi/v\d|dapi/v\d)/order", re.I)),
    ("binance withdraw/capital endpoint", re.compile(r"/sapi/v\d/(capital|asset)/", re.I)),
    ("coinbase orders endpoint",
     re.compile(r"(api\.exchange\.coinbase\.com|api\.coinbase\.com)[^\s'\"]*/orders", re.I)),
    ("coinbase brokerage API", re.compile(r"/api/v3/brokerage/", re.I)),
    ("exchange order call", re.compile(r"\b(create_order|createOrder|place_order|"
                                       r"placeOrder|submit_order)\s*\(")),
    ("withdrawal call", re.compile(r"\bwithdraw(al)?s?\s*\(", re.I)),
    ("exchange secret credential",
     re.compile(r"\b(BINANCE|COINBASE|KRAKEN|BYBIT|OKX|BROKER|EXCHANGE)_[A-Z_]*"
                r"(SECRET|PASSPHRASE|PRIVATE_KEY)\b")),
    ("ccxt library", re.compile(r"^\s*(import ccxt|from ccxt)|require\(['\"]ccxt['\"]\)",
                                re.M)),
]


def scan(root: pathlib.Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(p in SKIP_DIRS for p in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in ALLOWLIST:
            continue
        if path.suffix not in CODE_SUFFIXES and not path.name.startswith(".env"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS:
            for m in pattern.finditer(content):
                line = content.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line}: {label}: {m.group(0)!r}")
    return hits


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    hits = scan(root)
    for h in hits:
        print(h)
    if hits:
        print(f"\n{len(hits)} forbidden real-trading pattern(s) found (SRS §19.1).")
        return 1
    print("OK: no real-money execution patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
