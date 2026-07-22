"""Villanyan-Agent 3.0 — Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("schedule")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        """Validate cron expression: 5 or 6 space-separated fields."""
        parts = v.strip().split()
        if len(parts) not in (5, 6):
            raise ValueError(
                "Invalid cron expression: expected 5 or 6 space-separated fields"
            )
        allowed = {"*", ",", "-", "/", "0", "1", "2", "3", "4", "5", "6", "7",
                   "8", "9", "L", "W", "#", "?", "JAN", "FEB", "MAR", "APR",
                   "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
                   "SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}
        for part in parts:
            chars = set(part)
            if not chars <= allowed:
                invalid = chars - allowed
                raise ValueError(
                    f"Invalid characters in cron field: {''.join(sorted(invalid))}"
                )
        return v.strip()


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
