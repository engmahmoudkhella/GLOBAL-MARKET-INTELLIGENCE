from __future__ import annotations

from pydantic import BaseModel

from app.instruments.config_schema import InstrumentConfig


class ProviderMappingOut(BaseModel):
    provider: str
    provider_display_name: str
    provider_status: str
    provider_symbol: str
    purpose: str
    priority: int
    notes: str | None


class InstrumentOut(BaseModel):
    symbol: str
    display_name: str
    asset_class: str
    base_currency: str
    quote_currency: str
    role: str
    market_status: str
    enabled: bool
    configuration: InstrumentConfig
    providers: list[ProviderMappingOut]


class InstrumentList(BaseModel):
    items: list[InstrumentOut]
    total: int
