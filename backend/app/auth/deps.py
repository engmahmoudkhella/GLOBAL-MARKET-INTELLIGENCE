"""Auth dependencies: session cookie, CSRF (synchronizer token) and RBAC."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import service
from app.core import security
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, NotAuthenticated
from app.models import User, UserSession

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class Principal:
    user: User
    session: UserSession


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    s = get_settings()
    token = request.cookies.get(s.session_cookie_name)
    if not token:
        raise NotAuthenticated()
    resolved = service.resolve_session(db, token)
    if resolved is None:
        raise NotAuthenticated("Session expired or invalid")
    us, user = resolved
    if request.method not in SAFE_METHODS:
        header = request.headers.get(s.csrf_header_name, "")
        if not header or not security.tokens_equal(security.hash_token(header), us.csrf_token_hash):
            raise Forbidden("Missing or invalid CSRF token")
    return Principal(user=user, session=us)


def current_user(p: Principal = Depends(current_principal)) -> User:
    return p.user


def require_roles(*roles: str) -> Callable[[User], User]:
    def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise Forbidden("Insufficient role")
        return user

    return _dep


require_admin = require_roles("admin")
