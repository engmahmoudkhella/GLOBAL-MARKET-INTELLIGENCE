"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.api import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var

log = logging.getLogger("gmi.access")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    is_prod = settings.environment == "production"
    app = FastAPI(
        title="Global Market Intelligence API",
        version="0.1.0",
        description="Paper trading only. No real-money execution exists in this system.",
        docs_url=None if is_prod else "/api/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/api/openapi.json",
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.isascii() else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        log.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
        return response

    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()
