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


class TelegramAuthIn(BaseModel):
    init_data: str  # raw Telegram Web App initData query string


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


# -- write actions ------------------------------------------------------------
class OkOut(BaseModel):
    ok: bool
    status: Optional[str] = None


class SetBlockedIn(BaseModel):
    blocked: bool


class SetEnabledIn(BaseModel):
    enabled: bool


class ProxyActionIn(BaseModel):
    action: str  # enable | disable | reset_usage | revoke


# -- reports ------------------------------------------------------------------
class ReportPoint(BaseModel):
    date: str
    amount: int


class PaymentBreakdownItem(BaseModel):
    type: int
    type_name: str
    count: int
    amount: int


class TopServiceItem(BaseModel):
    id: int
    name: str
    count: int


class ReportsOut(BaseModel):
    days: int
    sales_total: int  # Σ non-draft invoices in range (value of what was sold)
    income_total: int  # Σ finished transactions' amount_paid (actual money in)
    orders: int  # subscriptions created in range
    new_users: int
    revenue_series: list[ReportPoint]
    payment_breakdown: list[PaymentBreakdownItem]
    top_services: list[TopServiceItem]


# -- resellers ----------------------------------------------------------------
class ResellerListItem(BaseModel):
    id: int
    username: Optional[str] = None
    name: Optional[str] = None
    role: int
    role_name: str
    balance: int
    children_count: int
    is_postpaid: bool
    is_blocked: bool
    created_at: Optional[datetime] = None


class ResellersPage(BaseModel):
    items: list[ResellerListItem]
    total: int


class ResellerDetail(ResellerListItem):
    available_credit: int
    max_post_paid_credit: int
    proxies_count: int
    parent_id: Optional[int] = None


# -- discounts ----------------------------------------------------------------
class DiscountListItem(BaseModel):
    id: int
    code: Optional[str] = None
    percentage: int
    is_active: bool
    on_purchase: bool
    on_renew: bool
    once_per_user: bool
    used_times: int
    use_counts: Optional[int] = None  # max uses (None = unlimited)
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DiscountsPage(BaseModel):
    items: list[DiscountListItem]
    total: int


# -- automation / broadcast ---------------------------------------------------
class BroadcastStatusOut(BaseModel):
    status: str  # idle | running | done | canceled | crashed
    kind: Optional[str] = None
    total: int = 0
    success: int = 0
    fails: int = 0
    sent: int = 0
    progress: int = 0  # percent
    started_by: Optional[int] = None


# -- settings (curated, safe subset) ------------------------------------------
class SettingsOut(BaseModel):
    access_only: bool
    referral_system: bool
    reset_password_button: bool
    show_connect_links_button: bool
    show_test_service_in_menu: bool
    phone_number_verify: bool
    delete_expired_users_after_days: int
    remind_invoices_each_n_days: int
    remind_invoices_after_amount: int
    default_daily_test_services: int
    referral_discount_percent: int
    cancel_payback_fee: int
    cancel_payback_days: int
    guardino_balance_warn: int
    guardino_balance_critical: int
    on_hold_timeout_seconds: int
    default_username_prefix: str
    username_generator: str
    transaction_logs: str
    orders_logs: str
    charge_amount_list: list[int]
    charge_amount_orders: list[int]
    alerts_enabled: bool
    notify_expiry_enabled: bool
    notify_expiry_days: int
    notify_low_data_enabled: bool
    notify_traffic_percent: int
    notify_data_remaining_gb: int
    notify_unused_enabled: bool
    notify_unused_days: int
    notify_ended_enabled: bool


class SettingsUpdateIn(BaseModel):
    access_only: Optional[bool] = None
    referral_system: Optional[bool] = None
    reset_password_button: Optional[bool] = None
    show_connect_links_button: Optional[bool] = None
    show_test_service_in_menu: Optional[bool] = None
    phone_number_verify: Optional[bool] = None
    delete_expired_users_after_days: Optional[int] = None
    remind_invoices_each_n_days: Optional[int] = None
    remind_invoices_after_amount: Optional[int] = None
    default_daily_test_services: Optional[int] = None
    referral_discount_percent: Optional[int] = None
    cancel_payback_fee: Optional[int] = None
    cancel_payback_days: Optional[int] = None
    guardino_balance_warn: Optional[int] = None
    guardino_balance_critical: Optional[int] = None
    on_hold_timeout_seconds: Optional[int] = None
    default_username_prefix: Optional[str] = None
    username_generator: Optional[str] = None
    transaction_logs: Optional[str] = None
    orders_logs: Optional[str] = None
    charge_amount_list: Optional[list[int]] = None
    charge_amount_orders: Optional[list[int]] = None
    alerts_enabled: Optional[bool] = None
    notify_expiry_enabled: Optional[bool] = None
    notify_expiry_days: Optional[int] = None
    notify_low_data_enabled: Optional[bool] = None
    notify_traffic_percent: Optional[int] = None
    notify_data_remaining_gb: Optional[int] = None
    notify_unused_enabled: Optional[bool] = None
    notify_unused_days: Optional[int] = None
    notify_ended_enabled: Optional[bool] = None


# -- audit log ----------------------------------------------------------------
class AuditListItem(BaseModel):
    id: int
    action: str
    source: str
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_role: int = 0
    actor_role_name: str = ""
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    amount: Optional[float] = None
    detail: Optional[dict] = None
    created_at: Optional[datetime] = None


class AuditPage(BaseModel):
    items: list[AuditListItem]
    total: int


# -- bot texts ----------------------------------------------------------------
class TextItem(BaseModel):
    key: str
    value: str
    variables: list[str] = []


class TextsOut(BaseModel):
    items: list[TextItem]


class TextUpdateIn(BaseModel):
    key: str
    value: str


# -- service menus (nested categories) ----------------------------------------
class MenuListItem(BaseModel):
    id: int
    title: str
    parent_id: Optional[int] = None
    purchase: bool = True
    renew: bool = True
    resellers_only: bool = False
    users_only: bool = False
    services_count: int = 0
    children_count: int = 0


class MenuDetail(MenuListItem):
    description: Optional[str] = None
    service_ids: list[int] = []


class MenusOut(BaseModel):
    items: list[MenuListItem]


class MenuCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    purchase: bool = True
    renew: bool = True
    resellers_only: bool = False
    users_only: bool = False
    service_ids: list[int] = []


class MenuUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    purchase: Optional[bool] = None
    renew: Optional[bool] = None
    resellers_only: Optional[bool] = None
    users_only: Optional[bool] = None
    service_ids: Optional[list[int]] = None


# -- bot buttons (main-menu labels) -------------------------------------------
class ButtonItem(BaseModel):
    key: str
    default: str
    value: str  # current custom label, or "" when using the default


class InlineButtonItem(BaseModel):
    key: str
    label: str  # built-in default label (for the editor)
    text: str = ""  # custom renamed text, or "" when using the default
    icon: str = ""  # configured custom_emoji_id, or ""
    style: str = ""  # configured colour (primary/success/danger), or ""
    default_style: str = ""


class ButtonsOut(BaseModel):
    items: list[ButtonItem]  # main-menu (reply) labels
    premium_enabled: bool = False
    inline: list[InlineButtonItem] = []  # inline buttons (premium emoji + colour)


class ButtonsUpdateIn(BaseModel):
    labels: Optional[dict[str, str]] = None  # key -> custom label ("" = default)
    premium_enabled: Optional[bool] = None
    icons: Optional[dict[str, str]] = None  # inline key -> custom_emoji_id
    styles: Optional[dict[str, str]] = None  # inline key -> style
    texts: Optional[dict[str, str]] = None  # inline key -> renamed text
