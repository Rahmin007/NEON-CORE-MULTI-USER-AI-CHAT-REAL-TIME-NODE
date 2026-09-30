"""Request and response shapes for the API (validated by Pydantic)."""
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class Role(str, Enum):
    ADMIN = "ADMIN"
    MODERATOR = "MODERATOR"
    USER = "USER"
    AI = "AI"  # the AI participant; never assigned to a human account


HUMAN_ROLES = (Role.USER, Role.MODERATOR, Role.ADMIN)
STAFF_ROLES = (Role.MODERATOR, Role.ADMIN)


# ---------- Auth & users ----------
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminCreateUser(RegisterRequest):
    role: Literal["USER", "MODERATOR", "ADMIN"] = "USER"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: Role
    is_active: bool
    muted_until: datetime | None = None
    created_at: datetime


class RoleUpdate(BaseModel):
    role: Literal["USER", "MODERATOR", "ADMIN"]


class StatusUpdate(BaseModel):
    is_active: bool


# ---------- Chat ----------
class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty.")
        return value


class MessageOut(BaseModel):
    id: str
    user_id: str | None
    username: str
    sender_role: Role
    message: str
    created_at: datetime


class OnlineUser(BaseModel):
    id: str
    username: str
    role: Role


class ModerationRequest(BaseModel):
    reason: str = Field(default="", max_length=300)


class MuteRequest(ModerationRequest):
    minutes: int = Field(default=10, ge=1, le=1440)


# ---------- Activity log ----------
class ActivityOut(BaseModel):
    id: str
    user_id: str | None
    username: str | None
    action: str
    details: dict[str, Any] | str | None
    ip_address: str | None
    created_at: datetime


class ActivityEventIn(BaseModel):
    action: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    details: dict[str, Any] | None = None

    @field_validator("details")
    @classmethod
    def small_details(cls, value: dict | None) -> dict | None:
        if value is not None and len(str(value)) > 1000:
            raise ValueError("details is too large")
        return value


class StatsOut(BaseModel):
    users: int
    active_users: int
    moderators: int
    admins: int
    messages: int
    online: int
