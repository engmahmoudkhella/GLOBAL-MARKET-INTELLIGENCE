from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.core.db import get_db
from app.instruments import service
from app.instruments.schemas import InstrumentList, InstrumentOut

router = APIRouter(
    prefix="/instruments", tags=["instruments"], dependencies=[Depends(current_user)]
)


@router.get("", response_model=InstrumentList)
def list_instruments(
    include_secondary: bool = Query(True, description="Include secondary series (BTCUSDT)"),
    db: Session = Depends(get_db),
) -> InstrumentList:
    items = service.list_instruments(db, include_secondary=include_secondary)
    return InstrumentList(items=items, total=len(items))


@router.get("/{symbol}", response_model=InstrumentOut)
def get_instrument(symbol: str, db: Session = Depends(get_db)) -> InstrumentOut:
    return service.get_instrument(db, symbol)
