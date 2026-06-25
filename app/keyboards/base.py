from aiogram.filters.callback_data import CallbackData
from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import config
from app.models.service import Service


class MainMenu(ReplyKeyboardBuilder):
    proxies = "📍 اشتراک‌های من"
    purchase = "🚀 خرید اشتراک"
    account = "💎 حساب من"
    charge = "💰 شارژ حساب"
    referral = "👥 زیرمجموعه گیری"
    help = "🗒 راهنما"
    support = "☑️ پشتیبانی"
    faq = "❓ سوالات متداول"
    back = "🔙 برگشت"
    cancel = "🚫 لغو"
    main_menu = "📱 منوی اصلی"
    admin_menu = "⚙️ پنل مدیریت"
    web_panel = "🖥 پنل وب"

    def __init__(
        self,
        test_services: list[Service],
        referral: bool = True,
        is_super_user: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(text=self.purchase)
        if test_services:
            for service in test_services:
                self.button(text=service.display_name)
        self.button(text=self.proxies)
        self.button(text=self.account)
        self.button(text=self.charge)
        if referral:
            self.button(text=self.referral)
        self.button(text=self.help)
        self.button(text=self.support)
        orders = [1]
        if test_services:
            orders.append(len(test_services))
        orders.append(3)
        if referral:
            orders.append(1)
        orders.append(2)
        if is_super_user:
            self.button(text=self.admin_menu)
            orders.append(1)
        if is_super_user and config.WEB_PANEL_URL:
            self.button(
                text=self.web_panel, web_app=WebAppInfo(url=config.WEB_PANEL_URL)
            )
            orders.append(1)
        self.adjust(*orders)


class CancelUserForm(ReplyKeyboardBuilder):
    def __init__(self, cancel: bool = False, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if cancel:
            self.button(text=MainMenu.cancel)
        else:
            self.button(text=MainMenu.back)
        self.button(text=MainMenu.main_menu)
        self.adjust(1, 1)


class ForceJoin(InlineKeyboardBuilder):
    check = "✅ بررسی عضویت"

    class Callback(CallbackData, prefix="check_force_join"):
        pass

    def __init__(self, force_join_chats: dict[str, str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for _, username in force_join_chats.items():
            self.button(text=f"🆔 @{username}", url=f"https://t.me/{username}")
        self.button(text=self.check, callback_data=self.Callback())
        self.adjust(1, 1)
