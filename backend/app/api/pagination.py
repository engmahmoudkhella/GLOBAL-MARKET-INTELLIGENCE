from __future__ import annotations

from fastapi import Query
from pydantic import BaseModel

MAX_LIMIT = 200


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(
    limit: int = Query(50, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0)
) -> PageParams:
    return PageParams(limit=limit, offset=offset)
