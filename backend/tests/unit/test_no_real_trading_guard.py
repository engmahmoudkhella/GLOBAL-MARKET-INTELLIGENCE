"""Runs the repository guard that forbids real-money execution code (SRS §19.1)."""

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location(
        "guard", ROOT / "scripts" / "check_no_real_trading.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_repository_has_no_real_trading_code():
    assert _load().scan(ROOT) == []


def test_guard_detects_forbidden_patterns(tmp_path):
    (tmp_path / "bad.py").write_text('requests.post("https://api.binance.com/api/v3/order")\n')
    (tmp_path / "bad2.ts").write_text("const BINANCE_API_SECRET = process.env.X\n")
    hits = _load().scan(tmp_path)
    assert len(hits) == 2
