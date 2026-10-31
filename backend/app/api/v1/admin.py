from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.health import readiness
from app.api.pagination import Page, PageParams, page_params
from app.auth.deps import require_admin
from app.core.db import get_db
from app.models import JobRun, MarketProvider

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class ProviderOut(BaseModel):
    """Provider status. Credentials and raw configuration are never included."""

    provider_name: str
    display_name: str
    provider_type: str
    status: str
    capabilities: list[str]
    licence_notes: str | None
    attribution: str | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    consecutive_failures: int


class JobRunOut(BaseModel):
    job_name: str
    idempotency_key: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None


@router.get("/providers", response_model=list[ProviderOut])
def providers(db: Session = Depends(get_db)) -> list[ProviderOut]:
    rows = db.scalars(select(MarketProvider).order_by(MarketProvider.id))
    return [
        ProviderOut(
            provider_name=p.provider_name,
            display_name=p.display_name,
            provider_type=p.provider_type,
            status=p.status,
            capabilities=list(p.capabilities),
            licence_notes=p.licence_notes,
            attribution=p.attribution,
            last_success_at=p.last_success_at,
            last_error_at=p.last_error_at,
            consecutive_failures=p.consecutive_failures,
        )
        for p in rows
    ]


@router.get("/jobs", response_model=Page[JobRunOut])
def jobs(page: PageParams = Depends(page_params), db: Session = Depends(get_db)) -> Page[JobRunOut]:
    total = db.scalar(select(func.count()).select_from(JobRun)) or 0
    rows = db.scalars(
        select(JobRun)
        .order_by(JobRun.started_at.desc(), JobRun.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    items = [
        JobRunOut(
            job_name=j.job_name,
            idempotency_key=j.idempotency_key,
            status=j.status,
            started_at=j.started_at,
            finished_at=j.finished_at,
            error=j.error,
        )
        for j in rows
    ]
    return Page[JobRunOut](items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/system-health")
def system_health() -> dict[str, Any]:
    return readiness()
