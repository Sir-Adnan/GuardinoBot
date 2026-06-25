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


# -- servers (panels) ---------------------------------------------------------
class ServerListItem(BaseModel):
    id: int
    name: Optional[str] = None
    host: str
    panel_type: str
    link_policy: Optional[str] = None
    is_enabled: bool
    total_proxies: int
    url: str


class ServerHealth(BaseModel):
    ok: bool
    username: Optional[str] = None
    is_sudo: Optional[bool] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


class ServersPage(BaseModel):
    items: list[ServerListItem]
    total: int


# -- services (plans) ---------------------------------------------------------
class ServiceListItem(BaseModel):
    id: int
    name: str
    data_limit: int
    expire_duration: int
    price: int
    purchaseable: bool
    renewable: bool
    is_test_service: bool
    resellers_only: bool
    server_id: int
    server_name: Optional[str] = None
    panel_type: Optional[str] = None


class ServicesPage(BaseModel):
    items: list[ServiceListItem]
    total: int


# -- proxies (subscriptions) --------------------------------------------------
class ProxyListItem(BaseModel):
    id: int
    username: str
    custom_name: Optional[str] = None
    status: str
    cost: Optional[int] = None
    user_id: int
    server_id: int
    server_name: Optional[str] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    created_at: Optional[datetime] = None


class ProxiesPage(BaseModel):
    items: list[ProxyListItem]
    total: int


# -- transactions (payments) --------------------------------------------------
class TransactionListItem(BaseModel):
    id: int
    type: int
    type_name: str
    status: int
    status_name: str
    amount: int
    amount_free_given: int
    amount_paid: Optional[int] = None
    user_id: int
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TransactionsPage(BaseModel):
    items: list[TransactionListItem]
    total: int
