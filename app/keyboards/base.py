from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.models.service import Service
from app.utils import buttons


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

    @staticmethod
    def _lbl(key: str) -> str:
        # Custom label set in the web panel, else the class default above. Lazy
        # import keeps app.utils.settings (→ app.main) out of module load order.
        from app.utils.settings import get_settings

        return buttons.resolve(key, get_settings().button_labels)

    def __init__(
        self,
        test_services: list[Service],
        referral: bool = True,
        is_super_user: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        from app.utils.settings import get_settings

        layout = buttons.resolve_main_layout(get_settings().main_menu_layout)
        rendered: set[str] = set()
        orders: list[int] = []
        for row in layout:
            count = 0
            for key in row:
                if key == "test_services":
                    for service in test_services:
                        self.button(text=service.display_name)
                        count += 1
                elif key == "referral":
                    if referral:
                        self.button(text=self._lbl("referral"))
                        count += 1
                        rendered.add(key)
                elif key == "admin_menu":
                    if is_super_user:
                        self.button(text=self._lbl("admin_menu"))
                        count += 1
                        rendered.add(key)
                elif key in buttons.MAIN_MENU_BUTTONS:
                    self.button(text=self._lbl(key))
                    count += 1
                    rendered.add(key)
            if count:
                orders.append(count)
        # A super-user must never lose the admin entry, even if a customer-focused
        # custom layout left it out.
        if is_super_user and "admin_menu" not in rendered:
            self.button(text=self._lbl("admin_menu"))
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
