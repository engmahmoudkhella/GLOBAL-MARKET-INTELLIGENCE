"""Authentication: no public signup (decision D2). Users are created via the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core import security
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.tz import validate_timezone
from app.models import User, UserSession
from app.models.user import LANGUAGES, ROLES


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime
    user: User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(
    session: Session,
    *,
    email: str,
    name: str,
    password: str,
    role: str = "viewer",
    preferred_language: str = "ar",
    timezone: str | None = None,
) -> User:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if preferred_language not in LANGUAGES:
        raise ValueError(f"preferred_language must be one of {LANGUAGES}")
    email_n = normalize_email(email)
    if "@" not in email_n:
        raise ValueError("invalid email")
    if session.scalar(select(User.id).where(User.email == email_n)) is not None:
        raise ValueError("a user with this email already exists")
    tz = validate_timezone(timezone or get_settings().default_timezone)
    user = User(
        email=email_n,
        name=name.strip(),
        password_hash=security.hash_password(password),
        role=role,
        preferred_language=preferred_language,
        timezone=tz,
    )
    session.add(user)
    session.flush()
    audit.record(
        session,
        "user.created",
        entity_type="user",
        entity_id=user.id,
        details={"role": role, "via": "cli"},
    )
    return user


def login(
    session: Session, email: str, password: str, *, ip: str | None, user_agent: str | None
) -> IssuedSession:
    email_n = normalize_email(email)
    user = session.scalar(select(User).where(User.email == email_n))
    if user is None:
        security.burn_verify_time(password)
        audit.record(session, "auth.login_failed", details={"reason": "unknown_email"}, ip=ip)
        session.commit()
        raise InvalidCredentials
    if not security.verify_password(user.password_hash, password) or not user.is_active:
        reason = "inactive" if user.is_active is False else "bad_password"
        audit.record(
            session, "auth.login_failed", user_id=user.id, details={"reason": reason}, ip=ip
        )
        session.commit()
        raise InvalidCredentials
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)

    now = utcnow()
    token, csrf = security.new_token(), security.new_token()
    expires = now + timedelta(hours=get_settings().session_ttl_hours)
    session.add(
        UserSession(
            token_hash=security.hash_token(token),
            csrf_token_hash=security.hash_token(csrf),
            user_id=user.id,
            expires_at=expires,
            ip=ip,
            user_agent=(user_agent or "")[:400] or None,
        )
    )
    user.last_login_at = now
    audit.record(session, "auth.login", user_id=user.id, ip=ip)
    session.commit()
    return IssuedSession(token, csrf, expires, user)


def resolve_session(session: Session, token: str) -> tuple[UserSession, User] | None:
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == security.hash_token(token))
    ).first()
    if row is None:
        return None
    us, user = row
    if us.revoked_at is not None or us.expires_at <= utcnow() or not user.is_active:
        return None
    return us, user


def logout(session: Session, us: UserSession, *, ip: str | None) -> None:
    session.execute(update(UserSession).where(UserSession.id == us.id).values(revoked_at=utcnow()))
    audit.record(session, "auth.logout", user_id=us.user_id, ip=ip)
    session.commit()


def set_password(session: Session, user: User, password: str) -> None:
    user.password_hash = security.hash_password(password)
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    audit.record(
        session,
        "user.password_changed",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        details={"via": "cli", "sessions_revoked": True},
    )
