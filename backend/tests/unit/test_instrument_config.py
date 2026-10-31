import pytest
from pydantic import ValidationError

from app.instruments.config_schema import InstrumentConfig

BASE = {
    "sessions": {"kind": "continuous"},
    "price_precision": 2,
    "staleness_seconds": 60,
    "candle_timeframes": ["1m", "1h"],
    "forecasting_enabled": True,
    "forecast_horizons": ["1h", "30d"],
}


def test_valid_config():
    cfg = InstrumentConfig.model_validate(BASE)
    assert cfg.forecast_horizons == ("1h", "30d")


@pytest.mark.parametrize(
    "patch",
    [
        {"forecast_horizons": ["15m"]},  # not a v1 horizon
        {"forecast_horizons": ["1h", "1h"]},  # duplicate
        {"forecasting_enabled": True, "forecast_horizons": []},
        {"forecasting_enabled": False},  # horizons without forecasting
        {"sessions": {"kind": "weekly"}},  # weekly without open/close
        {"sessions": {"kind": "continuous", "timezone": "Nope/Nope"}},
        {"unexpected": 1},  # extra keys forbidden
        {"staleness_seconds": 0},
    ],
)
def test_invalid_configs(patch):
    with pytest.raises(ValidationError):
        InstrumentConfig.model_validate({**BASE, **patch})
