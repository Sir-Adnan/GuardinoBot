"""Pydantic (v2) request/response models for the web panel."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    max_post_paid_credit: int = 0
    daily_test_services: int = 0
    discount_percentage: int = 0
    proxy_username_prefix: Optional[str] = None
    parent_id: Optional[int] = None
    referrer_id: Optional[int] = None


class UserUpdateIn(BaseModel):
    role: Optional[int] = None  # 0..3 — role change requires super-admin
    is_postpaid: Optional[bool] = None
    max_post_paid_credit: Optional[int] = None
    daily_test_services: Optional[int] = None
    discount_percentage: Optional[int] = None
    proxy_username_prefix: Optional[str] = None


class BalanceAdjustIn(BaseModel):
    amount: int  # > 0
    direction: str  # "charge" (add) | "decharge" (subtract)


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
    today_sales: int = 0  # Σ non-draft invoices today
    today_income: int = 0  # Σ finished tx amount_paid today
    month_sales: int = 0
    month_income: int = 0
    servers_total: int = 0
    servers_enabled: int = 0
    pending_payments: int = 0  # non-finished tx in last 30d
    orders_today: int = 0  # subscriptions created today
    revenue_spark: list[int] = []  # last 14 days' invoice totals (oldest→newest)
    total_sales: int = 0  # all-time Σ non-draft invoices
    total_income: int = 0  # all-time Σ finished tx amount_paid
    active_users: int = 0  # users with ≥1 active subscription
    resellers_total: int = 0
    period_today: Optional["PeriodStat"] = None
    period_week: Optional["PeriodStat"] = None
    period_month: Optional["PeriodStat"] = None


class PeriodStat(BaseModel):
    income: int = 0  # Σ finished tx amount_paid in the period
    sales: int = 0  # Σ non-draft invoices in the period
    orders: int = 0  # subscriptions created in the period
    gb: float = 0  # GB of data sold (Σ service.data_limit of created subs)


DashboardOut.model_rebuild()


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


class ServerDetail(ServerListItem):
    port: Optional[int] = None
    https: bool = False
    username: Optional[str] = None  # admin/reseller login name (NEVER the password/token)
    services_count: int = 0
    proxies_count: int = 0


class ServerCreateIn(BaseModel):
    host: str
    port: Optional[int] = None
    https: bool = False
    panel_type: str  # marzban | pasarguard | guardino
    username: str
    password: str
    name: Optional[str] = None
    link_policy: Optional[str] = None  # guardino: master_first | node_first


class ServerUpdateIn(BaseModel):
    name: Optional[str] = None
    is_enabled: Optional[bool] = None
    link_policy: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    https: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None  # provided → re-connect + refresh token


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
    button_icon: Optional[str] = None  # premium custom_emoji_id for this service's button
    button_style: Optional[str] = None  # button colour: primary/success/danger


class ServicesPage(BaseModel):
    items: list[ServiceListItem]
    total: int


class ServiceDetail(ServiceListItem):
    all_inbounds: bool = False
    inbounds: Optional[Any] = None  # raw provisioning (Marzban) — read-only here
    panel_config: Optional[Any] = None  # PasarGuard groups / Guardino nodes — read-only
    flow: Optional[str] = None
    one_time_only: bool = False
    users_only: bool = False
    create_on_hold_users: bool = False
    usage_reset_strategy: str = "no_reset"
    append_available_data_renew: bool = False
    priority: int = 0
    proxies_count: int = 0  # how many proxies reference it (delete guard)
    reserves_count: int = 0  # active reserves (RESTRICT — block delete)


class ServiceUpdateIn(BaseModel):
    name: Optional[str] = None
    data_limit: Optional[int] = None
    expire_duration: Optional[int] = None
    price: Optional[int] = None
    purchaseable: Optional[bool] = None
    renewable: Optional[bool] = None
    is_test_service: Optional[bool] = None
    one_time_only: Optional[bool] = None
    resellers_only: Optional[bool] = None
    users_only: Optional[bool] = None
    create_on_hold_users: Optional[bool] = None
    usage_reset_strategy: Optional[str] = None
    append_available_data_renew: Optional[bool] = None
    flow: Optional[str] = None  # "" / "none" → no flow; "xtls-rprx-vision"
    button_icon: Optional[str] = None
    button_style: Optional[str] = None


class ServiceReorderIn(BaseModel):
    ids: list[int]  # full ordered list of service ids → priority = index


class ServiceButtonUpdateIn(BaseModel):
    button_icon: Optional[str] = None  # "" clears
    button_style: Optional[str] = None  # ""/"none" clears; primary/success/danger


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
    start: Optional[str] = None  # effective range (ISO date), echoed back
    end: Optional[str] = None
    sales_total: int  # Σ non-draft invoices in range (value of what was sold)
    income_total: int  # Σ finished transactions' amount_paid (actual money in)
    orders: int  # subscriptions created in range
    new_users: int
    failed_payments: int  # non-finished transactions created in range
    gb_sold: float = 0  # GB provisioned by subs created in range (Σ service.data_limit)
    # all-time totals (ignore the range — lifetime figures)
    all_sales_total: int = 0
    all_income_total: int = 0
    all_orders: int = 0  # total subscriptions ever created
    all_users: int = 0
    all_gb_sold: float = 0
    # subscription (proxy) stats — current state, not range-bound
    proxies_total: int = 0
    proxies_active: int = 0
    proxies_by_status: dict[str, int] = {}
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


class PromoteResellerIn(BaseModel):
    identifier: str  # numeric id or @username of the user to promote


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


class DiscountCreateIn(BaseModel):
    code: Optional[str] = None  # blank → auto-generated
    percentage: int
    on_purchase: bool = True
    on_renew: bool = False
    once_per_user: bool = False
    use_counts: Optional[int] = None  # null = unlimited
    expires_at: Optional[datetime] = None
    is_active: bool = True


class DiscountUpdateIn(BaseModel):
    code: Optional[str] = None
    percentage: Optional[int] = None
    on_purchase: Optional[bool] = None
    on_renew: Optional[bool] = None
    once_per_user: Optional[bool] = None
    use_counts: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


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


class AlertsStatusOut(BaseModel):
    state: str = "idle"  # idle | running | done | deferred | disabled
    last_run: Optional[str] = None  # ISO datetime of the last scan
    sent: int = 0  # alerts sent on the last finished scan


class AlertPreviewItem(BaseModel):
    type: str  # alert_expiry | alert_low_data | alert_unused | alert_ended
    text: str  # rendered HTML (sample values filled in)
    is_default: bool = False  # True when the row is empty → bot uses its built-in


class AlertPreviewOut(BaseModel):
    items: list[AlertPreviewItem]


class AlertConfigTextItem(BaseModel):
    key: str
    value: str
    variables: list[str] = []


class AlertConfigButtonItem(BaseModel):
    key: str
    label: str  # default button label (for display)
    icon: str = ""  # custom/premium emoji id
    style: str = ""  # "" | none | primary | success | danger
    default_style: str = ""


class AlertConfigOut(BaseModel):
    texts: list[AlertConfigTextItem]
    buttons: list[AlertConfigButtonItem]
    premium_enabled: bool = False  # inline premium master switch
    cadence: dict[str, int] = {}  # base type -> re-send hours (0 = once)


class AlertConfigUpdateIn(BaseModel):
    texts: Optional[dict[str, str]] = None  # alert text key -> value
    icons: Optional[dict[str, str]] = None  # alert button key -> emoji id
    styles: Optional[dict[str, str]] = None  # alert button key -> style
    premium_enabled: Optional[bool] = None
    cadence: Optional[dict[str, int]] = None  # base type -> hours


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
    notify_expiry_steps_hours: list[int]
    alerts_quiet_enabled: bool
    alerts_quiet_start_hour: int
    alerts_quiet_end_hour: int


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
    notify_expiry_steps_hours: Optional[list[int]] = None
    alerts_quiet_enabled: Optional[bool] = None
    alerts_quiet_start_hour: Optional[int] = None
    alerts_quiet_end_hour: Optional[int] = None


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
    group: str = ""  # tab/category (general/sales/support/access/alerts)


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
    button_icon: Optional[str] = None  # premium custom_emoji_id for this category's button
    button_style: Optional[str] = None  # button colour: primary/success/danger


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
    button_icon: Optional[str] = None
    button_style: Optional[str] = None


class MenuUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    purchase: Optional[bool] = None
    renew: Optional[bool] = None
    resellers_only: Optional[bool] = None
    users_only: Optional[bool] = None
    service_ids: Optional[list[int]] = None
    button_icon: Optional[str] = None
    button_style: Optional[str] = None


# -- bot buttons (main-menu labels) -------------------------------------------
class ButtonItem(BaseModel):
    key: str
    default: str
    value: str  # current custom label, or "" when using the default
    icon: str = ""  # configured custom_emoji_id, or "" (reply-button premium)
    style: str = ""  # configured colour / "none", or "" for default
    default_style: str = ""


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
    reply_premium_enabled: bool = False  # experimental: premium on reply buttons
    inline: list[InlineButtonItem] = []  # inline buttons (premium emoji + colour)
    # Effective main-menu layout: ordered rows of keys (default-resolved). Keys
    # are ButtonItem keys + the "test_services" dynamic placeholder.
    main_layout: list[list[str]] = []


class ButtonsUpdateIn(BaseModel):
    labels: Optional[dict[str, str]] = None  # key -> custom label ("" = default)
    premium_enabled: Optional[bool] = None
    reply_premium_enabled: Optional[bool] = None
    icons: Optional[dict[str, str]] = None  # inline key -> custom_emoji_id
    styles: Optional[dict[str, str]] = None  # inline key -> style
    texts: Optional[dict[str, str]] = None  # inline key -> renamed text
    main_layout: Optional[list[list[str]]] = None  # rows of main-menu keys ([] = default)
