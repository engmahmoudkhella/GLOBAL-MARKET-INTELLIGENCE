"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.audit import AuditLog, JobRun
from app.models.base import Base
from app.models.instrument import Instrument, InstrumentProviderSymbol, MarketProvider
from app.models.market import (
    BoiPublicationObservation,
    DataQualityEvent,
    MarketCandle,
    MarketHoliday,
    MarketQuote,
    OfficialReferenceRate,
    SpecialClosure,
)
from app.models.user import User, UserSession

__all__ = [
    "AuditLog",
    "Base",
    "BoiPublicationObservation",
    "DataQualityEvent",
    "Instrument",
    "InstrumentProviderSymbol",
    "JobRun",
    "MarketCandle",
    "MarketHoliday",
    "MarketQuote",
    "MarketProvider",
    "OfficialReferenceRate",
    "SpecialClosure",
    "User",
    "UserSession",
]
