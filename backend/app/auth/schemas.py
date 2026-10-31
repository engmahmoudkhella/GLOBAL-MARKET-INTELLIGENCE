from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str
    preferred_language: str
    timezone: str
    last_login_at: datetime | None


class LoginResponse(BaseModel):
    user: UserOut
    expires_at: datetime
