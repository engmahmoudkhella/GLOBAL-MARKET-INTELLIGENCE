"""Structured errors as RFC 9457 problem+json."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

log = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    title = "Bad request"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class NotAuthenticated(AppError):
    status_code, code, title = 401, "not_authenticated", "Authentication required"


class Forbidden(AppError):
    status_code, code, title = 403, "forbidden", "Forbidden"


class NotFound(AppError):
    status_code, code, title = 404, "not_found", "Not found"


class RateLimited(AppError):
    status_code, code, title = 429, "rate_limited", "Too many requests"


def problem(status: int, code: str, title: str, detail: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": request_id_var.get(),
    }
    body.update(extra)
    headers = {}
    if status == 429 and "retry_after" in extra:
        headers["Retry-After"] = str(extra["retry_after"])
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return problem(exc.status_code, exc.code, exc.title, exc.detail, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return problem(
            422, "validation_error", "Invalid request", "Validation failed", errors=errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, f"http_{exc.status_code}", str(exc.detail), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return problem(
            500, "internal_error", "Internal server error", "An unexpected error occurred"
        )
