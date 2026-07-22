"""Villanyan-Agent 3.0 — Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = ""
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None


class MessageResponse(BaseModel):
    detail: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 50


class CronJobCreate(BaseModel):
    name: str = Field(..., max_length=128)
    schedule: str = Field(..., max_length=64)
    command: str = Field(..., max_length=512)
    active: bool = True


class CronJobUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    command: Optional[str] = None
    active: Optional[bool] = None


class ReminderCreate(BaseModel):
    text: str = Field(..., max_length=512)
    priority: int = 0
    due_date: Optional[datetime] = None


class ReminderUpdate(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None


class CostRateCreate(BaseModel):
    model: str = Field(..., max_length=128)
    price_in: float = 0.0
    price_out: float = 0.0
    currency: str = "USD"


class SecurityBaselineCreate(BaseModel):
    path: str = Field(..., max_length=1024)
    expected_perm: str = Field(..., max_length=16)


class MemoryFileVersionCreate(BaseModel):
    file_name: str = Field(..., max_length=256)
    content: str
    diff: Optional[str] = None
