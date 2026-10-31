from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import Principal, current_principal, current_user
from app.auth.schemas import LoginRequest, LoginResponse, UserOut
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import NotAuthenticated
from app.core.rate_limit import client_ip, login_limit
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, issued: service.IssuedSession) -> None:
    s = get_settings()
    max_age = s.session_ttl_hours * 3600
    response.set_cookie(
        s.session_cookie_name,
        issued.token,
        max_age=max_age,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )
    # Readable by the frontend so it can echo it in the CSRF header.
    response.set_cookie(
        s.csrf_cookie_name,
        issued.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=s.cookie_secure,
        samesite="strict",
        path="/",
    )


def _clear_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(login_limit)])
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    try:
        issued = service.login(
            db,
            body.email,
            body.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except service.InvalidCredentials:
        raise NotAuthenticated("Invalid email or password") from None
    _set_cookies(response, issued)
    return LoginResponse(user=UserOut.model_validate(issued.user), expires_at=issued.expires_at)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
) -> Response:
    service.logout(db, principal.session, ip=client_ip(request))
    response.status_code = 204
    _clear_cookies(response)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
