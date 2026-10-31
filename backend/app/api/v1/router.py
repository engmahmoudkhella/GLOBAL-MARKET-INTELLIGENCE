from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import admin, auth, instruments
from app.core.rate_limit import default_limit

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(default_limit)])
api_router.include_router(auth.router)
api_router.include_router(instruments.router)
api_router.include_router(admin.router)
