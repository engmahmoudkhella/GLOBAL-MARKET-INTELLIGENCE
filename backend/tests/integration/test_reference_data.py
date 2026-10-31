import pytest
from sqlalchemy import select

from app.instruments.config_schema import InstrumentConfig
from app.models import Instrument, InstrumentProviderSymbol, MarketProvider

pytestmark = pytest.mark.integration


def test_seeded_instruments_and_configs_are_valid(db):
    insts = {i.symbol: i for i in db.scalars(select(Instrument))}
    assert set(insts) == {"USDILS", "XAUUSD", "BTCUSD", "BTCUSDT"}
    for inst in insts.values():
        InstrumentConfig.model_validate(inst.configuration_json)
    assert {s for s, i in insts.items() if i.role == "primary"} == {"USDILS", "XAUUSD", "BTCUSD"}


def test_seed_contains_no_prices(db):
    """Configuration only: no price-like keys anywhere in seeded config."""
    for inst in db.scalars(select(Instrument)):
        flat = str(inst.configuration_json).lower()
        for word in ('price":', "'last'", "'bid'", "'ask'", "'close'"):
            assert word not in flat


def test_usdils_has_30d_horizon(db):
    cfg = InstrumentConfig.model_validate(
        db.scalar(select(Instrument).where(Instrument.symbol == "USDILS")).configuration_json
    )
    assert "30d" in cfg.forecast_horizons
    assert set(cfg.forecast_horizons) == {"1h", "4h", "24h", "7d", "30d"}


def test_btcusd_uses_only_usd_quoted_sources(db):
    """Binance USDT data must never be mapped onto BTCUSD (plan §0.2)."""
    rows = db.execute(
        select(Instrument.symbol, MarketProvider.provider_name)
        .join(InstrumentProviderSymbol, InstrumentProviderSymbol.instrument_id == Instrument.id)
        .join(MarketProvider, MarketProvider.id == InstrumentProviderSymbol.provider_id)
    ).all()
    btcusd = {p for s, p in rows if s == "BTCUSD"}
    assert btcusd == {"coinbase", "coingecko"}
    assert {p for s, p in rows if s == "BTCUSDT"} == {"binance"}
    usdt = db.scalar(select(Instrument).where(Instrument.symbol == "BTCUSDT"))
    assert usdt.quote_currency == "USDT" and usdt.role == "secondary"
    assert InstrumentConfig.model_validate(usdt.configuration_json).forecasting_enabled is False


def test_providers_have_no_declared_capabilities_before_adapters_exist(db):
    for p in db.scalars(select(MarketProvider)):
        assert p.capabilities == []
        assert p.status == "not_configured"
