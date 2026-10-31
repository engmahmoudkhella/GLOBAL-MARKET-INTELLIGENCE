from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

ROLES = ("admin", "analyst", "viewer")
LANGUAGES = ("ar", "en")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','analyst','viewer')", name="role"),
        CheckConstraint("preferred_language IN ('ar','en')", name="preferred_language"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="viewer")
    preferred_language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="ar")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Asia/Gaza")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
