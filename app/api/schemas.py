"""Pydantic (v2) request/response models for the web panel."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

ROLE_NAMES = {0: "user", 1: "reseller", 2: "admin", 3: "super_user"}


# -- auth ---------------------------------------------------------------------
class RequestCodeIn(BaseModel):
    identifier: str  # Telegram numeric id or @username


class VerifyIn(BaseModel):
    identifier: str
    code: str


class RefreshIn(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: int
    username: Optional[str] = None
    name: Optional[str] = None
    role: int
    role_name: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: MeOut


# -- users --------------------------------------------------------------------
class UserListItem(BaseModel):
    id: int
    username: Optional[str] = None
    name: Optional[str] = None
    role: int
    role_name: str
    is_blocked: bool
    blocked_bot: bool
    created_at: Optional[datetime] = None


class UserDetail(UserListItem):
    balance: int = 0
    is_verified: bool = False
    is_postpaid: bool = False
    proxies_count: int = 0


class UsersPage(BaseModel):
    items: list[UserListItem]
    total: int


# -- dashboard ----------------------------------------------------------------
class DashboardOut(BaseModel):
    users_total: int
    users_today: int
    users_month: int
    proxies_total: int
    proxies_active: int
    blocked_users: int
