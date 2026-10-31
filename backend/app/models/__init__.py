"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.audit import AuditLog, JobRun
from app.models.base import Base
from app.models.instrument import Instrument, InstrumentProviderSymbol, MarketProvider
from app.models.market import (
    DataQualityEvent,
    MarketCandle,
    MarketHoliday,
    MarketQuote,
    OfficialReferenceRate,
)
from app.models.user import User, UserSession

__all__ = [
    "AuditLog",
    "Base",
    "DataQualityEvent",
    "Instrument",
    "InstrumentProviderSymbol",
    "JobRun",
    "MarketCandle",
    "MarketHoliday",
    "MarketQuote",
    "MarketProvider",
    "OfficialReferenceRate",
    "User",
    "UserSession",
]
