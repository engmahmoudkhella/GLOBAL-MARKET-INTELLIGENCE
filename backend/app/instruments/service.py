from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.instruments.config_schema import InstrumentConfig
from app.instruments.schemas import InstrumentOut, ProviderMappingOut
from app.models import Instrument, InstrumentProviderSymbol, MarketProvider


def _to_out(session: Session, inst: Instrument) -> InstrumentOut:
    rows = session.execute(
        select(InstrumentProviderSymbol, MarketProvider)
        .join(MarketProvider, MarketProvider.id == InstrumentProviderSymbol.provider_id)
        .where(InstrumentProviderSymbol.instrument_id == inst.id)
        .order_by(InstrumentProviderSymbol.priority)
    ).all()
    return InstrumentOut(
        symbol=inst.symbol,
        display_name=inst.display_name,
        asset_class=inst.asset_class,
        base_currency=inst.base_currency,
        quote_currency=inst.quote_currency,
        role=inst.role,
        market_status=inst.market_status,
        enabled=inst.enabled,
        configuration=InstrumentConfig.model_validate(inst.configuration_json),
        providers=[
            ProviderMappingOut(
                provider=p.provider_name,
                provider_display_name=p.display_name,
                provider_status=p.status,
                provider_symbol=m.provider_symbol,
                purpose=m.purpose,
                priority=m.priority,
                notes=m.notes,
            )
            for m, p in rows
        ],
    )


def list_instruments(session: Session, include_secondary: bool = True) -> list[InstrumentOut]:
    stmt = select(Instrument).order_by(Instrument.role, Instrument.id)
    if not include_secondary:
        stmt = stmt.where(Instrument.role == "primary")
    return [_to_out(session, i) for i in session.scalars(stmt)]


def get_instrument(session: Session, symbol: str) -> InstrumentOut:
    inst = session.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if inst is None:
        raise NotFound(f"Unknown instrument '{symbol}'")
    return _to_out(session, inst)
