from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import config
from app.keyboards import base
from app.keyboards.admin import server, service
from app.keyboards.premium import premium_button


class AdminPanelAction(str, Enum):
    servers = "servers"
    services = "services"
    service_menues = "service_menues"
    proxies = "proxies"
    users = "users"
    payments = "payments"
    cards = "cards"
    panel = "panel"
    settings = "settings"
    stats = "stats"


class AdminPanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="admin"):
        action: AdminPanelAction

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if config.WEB_PANEL_URL:
            self.add(
                premium_button(
                    text="🖥 پنل وب مدیریت",
                    key="admin_web_panel",
                    web_app=WebAppInfo(url=config.WEB_PANEL_URL),
                )
            )
        self.add(
            premium_button(
                text="مدیریت سرورها",
                key="admin_servers",
                callback_data=self.Callback(action=AdminPanelAction.servers),
            )
        )
        self.add(
            premium_button(
                text="مدیریت سرویس‌ها",
                key="admin_services",
                callback_data=self.Callback(action=AdminPanelAction.services),
            )
        )
        self.add(
            premium_button(
                text="دسته بندی سرویس‌ها",
                key="admin_service_menues",
                callback_data=self.Callback(action=AdminPanelAction.service_menues),
            )
        )
        self.add(
            premium_button(
                text="مدیریت کاربران",
                key="admin_users",
                callback_data=self.Callback(action=AdminPanelAction.users),
            )
        )
        self.add(
            premium_button(
                text="مدیریت پرداخت‌ها",
                key="admin_payments",
                callback_data=self.Callback(action=AdminPanelAction.payments),
            )
        )
        self.add(
            premium_button(
                text="تنظیمات",
                key="admin_settings",
                callback_data=self.Callback(action=AdminPanelAction.settings),
            )
        )
        self.add(
            premium_button(
                text="وضعیت",
                key="admin_stats",
                callback_data=self.Callback(action=AdminPanelAction.stats),
            )
        )
        if config.WEB_PANEL_URL:
            self.adjust(1, 2, 1, 2, 1)
        else:
            self.adjust(2, 1, 2, 1)


class BulkUpdateProxiesProc(str, Enum):
    data_limit = "data_limit"
    expire = "expire"
    inc = "inc"
    dec = "dec"
    enter_value = "enter_value"

    proceed = "proceed"


class BulkUpdateProxies(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="blkupdt"):
        category: Literal["service", "server"] = "server"
        field: Literal["data_limit", "expire"] | None = None
        action: Literal["inc", "dec"] | None = None
        value: int | None = None
        proc: BulkUpdateProxiesProc
        server_id: int | None = None
        service_id: int | None = None

    def __init__(
        self,
        category: Literal["service", "server"],
        field: Literal["data_limit", "expire"],
        action: Literal["inc", "dec"],
        value: int | None,
        service_id: int | None = None,
        server_id: int | None = None,
        proceed_button: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="کدام یک از مقادیرتغییر کند؟",
            callback_data="ph",
        )
        self.button(
            text=f"حجم {'✅' if field == 'data_limit' else ''}",
            callback_data=self.Callback(
                category=category,
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateProxiesProc.data_limit,
                server_id=server_id,
                service_id=service_id,
            ),
        )
        self.button(
            text=f"زمان {'✅' if field == 'expire' else ''}",
            callback_data=self.Callback(
                category=category,
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateProxiesProc.expire,
                server_id=server_id,
                service_id=service_id,
            ),
        )
        self.button(
            text="چه عملیاتی انجام شود؟",
            callback_data="ph",
        )
        self.button(
            text=f"افزایش {'✅' if action == 'inc' else ''}",
            callback_data=self.Callback(
                category=category,
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateProxiesProc.inc,
                server_id=server_id,
                service_id=service_id,
            ),
        )
        self.button(
            text=f"کاهش {'✅' if action == 'dec' else ''}",
            callback_data=self.Callback(
                category=category,
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateProxiesProc.dec,
                server_id=server_id,
                service_id=service_id,
            ),
        )
        self.button(
            text="وارد کردن مقدار",
            callback_data=self.Callback(
                category=category,
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateProxiesProc.enter_value,
                server_id=server_id,
                service_id=service_id,
            ),
        )
        if proceed_button:
            self.button(
                text="⚠️ اجرای دستور ⚠️",
                callback_data=self.Callback(
                    category=category,
                    field=field,
                    action=action,
                    value=value,
                    proc=BulkUpdateProxiesProc.proceed,
                    server_id=server_id,
                    service_id=service_id,
                ),
            )
        if category == "server":
            self.button(
                text="برگشت",
                callback_data=server.Servers.Callback(
                    server_id=server_id, action=server.ServersAction.show
                ),
            )
        else:
            self.button(
                text="برگشت",
                callback_data=service.Services.Callback(
                    service_id=service_id, action=service.ServicesAction.show
                ),
            )
        self.adjust(1, 2, 1, 2, 1, 1)


class LogPanelDuration(str, Enum):
    today = "today"
    this_week = "this_week"
    this_month = "this_month"
    last_24_h = "last_24"
    last_7_d = "last_7"
    last_30_d = "last_30"


class LogPanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="lgpnldu"):
        duration: LogPanelDuration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="امروز",
            callback_data=self.Callback(duration=LogPanelDuration.today),
        )
        self.button(
            text="هفته جاری",
            callback_data=self.Callback(duration=LogPanelDuration.this_week),
        )
        self.button(
            text="ماه جاری",
            callback_data=self.Callback(duration=LogPanelDuration.this_month),
        )
        self.button(
            text="۲۴ ساعت گذشته",
            callback_data=self.Callback(duration=LogPanelDuration.last_24_h),
        )
        self.button(
            text="۷ روز گذشته",
            callback_data=self.Callback(duration=LogPanelDuration.last_7_d),
        )
        self.button(
            text="۳۰ روز گذشته",
            callback_data=self.Callback(duration=LogPanelDuration.last_30_d),
        )
        self.adjust(1)


class Stats(InlineKeyboardBuilder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="Back",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.panel),
        )
        self.adjust(1, 1)


class CancelFormAdmin(ReplyKeyboardBuilder):
    cancel = "لغو"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text=self.cancel)
        self.button(text=base.MainMenu.admin_menu)
        self.adjust(1, 1)


class YesOrNoFormAdmin(ReplyKeyboardBuilder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="بله")
        self.button(text="خیر")
        self.button(text=CancelFormAdmin.cancel)
        self.adjust(2, 1)
