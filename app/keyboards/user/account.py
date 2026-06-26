from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.keyboards.premium import premium_button
from app.keyboards.user import proxy
from app.models.user import User

from .. import base


class UserPanelAction(str, Enum):
    show = "show"
    charge = "charge"
    referral = "referral"
    proxies = "proxies"
    redeem_code = "redeem"
    settings = "settings"
    manage_users = "manage_users"


class UserPanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="account"):
        action: UserPanelAction
        service_id: int = 0
        menu_id: int = 0
        proxy_id: int = 0
        user_id: int | None = None
        current_page: int = 0
        mode: Literal["purchase", "renew", "reserve"] | None = None

    def __init__(self, user: User, referral: bool = True, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="💳 شارژ حساب",
                key="account_charge",
                callback_data=self.Callback(action=UserPanelAction.charge),
            )
        )
        if referral:
            self.add(
                premium_button(
                    text="💎 زیرمجموعه گیری",
                    key="account_referral",
                    callback_data=self.Callback(action=UserPanelAction.referral),
                )
            )
        self.add(
            premium_button(
                text="📍 اشتراک‌های من",
                key="account_proxies",
                callback_data=self.Callback(action=UserPanelAction.proxies),
            )
        )
        self.add(
            premium_button(
                text="🎁 ثبت کد تخفیف",
                key="account_redeem",
                callback_data=self.Callback(action=UserPanelAction.redeem_code),
            )
        )

        if user.role > User.Role.reseller:
            self.add(
                premium_button(
                    text="⚙️ تنظیمات حساب",
                    key="account_settings",
                    callback_data=self.Callback(action=UserPanelAction.settings),
                )
            )
        if user.role > User.Role.reseller:
            self.add(
                premium_button(
                    text="👥 مدیریت کاربران",
                    key="account_manage_users",
                    callback_data=ManageUsers.Callback(
                        current_page=0,
                        action=ManageUsersAction.all,
                    ),
                )
            )
        self.adjust(1, 1, 1, 2)


class RefPanel(InlineKeyboardBuilder):
    def __init__(self, user: User, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="🔙 برگشت",
            callback_data=UserPanel.Callback(action=UserPanelAction.show),
        )


class ManageUsersAction(str, Enum):
    all = "all"
    show_user = "show_user"


class ManageUsers(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="mngusrs"):
        user_id: int = 0
        current_page: int = 0
        action: ManageUsersAction = ManageUsersAction.all

    def __init__(
        self,
        users: list[User],
        current_page: int = 0,
        next_page: bool = False,
        prev_page: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for user in users:
            self.button(
                text=f"{f'@{user.username}' if user.username else user.name} | {user.id}",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUsersAction.show_user,
                ),
            )

        if next_page:
            self.button(
                text="➡️ صفحه بعد",
                callback_data=self.Callback(
                    current_page=current_page + 1,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ صفحه قبل",
                callback_data=self.Callback(
                    current_page=current_page - 1,
                ),
            )
        self.button(
            text="🔙 برگشت",
            callback_data=UserPanel.Callback(action=UserPanelAction.show),
        )
        self.adjust(
            *[1 for _ in range(10)], 2, 1
        )  # only the last row has 2 items (prev and next buttons)


class ManageUserAction(str, Enum):
    charge = "charge"
    discount_percent = "discount_percent"
    max_test_services = "max_test_services"
    proxy_prefix = "proxy_prefix"


class ManageUser(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="mngusrr"):
        user_id: int
        parent_id: int
        current_page: int = 0
        action: ManageUserAction = ManageUserAction.charge

    def __init__(
        self,
        user: User,
        parent_id: int,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="پروکسی‌ها",
            callback_data=proxy.Proxies.Callback(
                user_id=user.id,
                parent_id=parent_id,
                action=proxy.ProxiesActions.show,
                current_page=0,
            ),
        )
        self.button(
            text="شارژ حساب",
            callback_data=self.Callback(
                user_id=user.id,
                parent_id=parent_id,
                action=ManageUserAction.charge,
                current_page=current_page,
            ),
        )
        self.button(
            text="درصد تخفیف",
            callback_data=self.Callback(
                user_id=user.id,
                parent_id=parent_id,
                action=ManageUserAction.discount_percent,
                current_page=current_page,
            ),
        )
        self.button(
            text="پیشوند پروکسی‌ها",
            callback_data=self.Callback(
                user_id=user.id,
                parent_id=parent_id,
                action=ManageUserAction.proxy_prefix,
                current_page=current_page,
            ),
        )
        if user.role == User.Role.reseller:
            self.button(
                text="تعداد دریافت سرویس‌‌های تست",
                callback_data=self.Callback(
                    user_id=user.id,
                    parent_id=parent_id,
                    action=ManageUserAction.max_test_services,
                    current_page=current_page,
                ),
            )
        self.button(
            text="🔙 برگشت",
            callback_data=ManageUsers.Callback(
                current_page=current_page, action=ManageUsersAction.all
            ),
        )
        self.adjust(1, 1)


class ChargeByParent(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="chrgprntconf"):
        user_id: int
        parent_id: int
        amount: int
        current_page: int = 0

    def __init__(
        self,
        user_id: User,
        parent_id: int,
        amount: int,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="✅ تأیید",
            callback_data=self.Callback(
                user_id=user_id,
                parent_id=parent_id,
                amount=amount,
                current_page=current_page,
            ),
        )
        self.button(
            text="🔙 برگشت",
            callback_data=ManageUsers.Callback(
                current_page=current_page, action=ManageUsersAction.all
            ),
        )
        self.adjust(1, 1)


class UserSettingsAction(str, Enum):
    username_prefix = "username_prefix"


class UserSettings(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="usrstngs"):
        user_id: int
        parent_id: int | None = None
        current_page: int = 0
        action: UserSettingsAction

    def __init__(
        self,
        user: User,
        parent_id: int = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تنظیم پیشوند پروکسی",
            callback_data=self.Callback(
                user_id=user.id,
                parent_id=parent_id,
                current_page=current_page,
                action=UserSettingsAction.username_prefix,
            ),
        )
        self.button(
            text="🔙 برگشت",
            callback_data=UserPanel.Callback(action=UserPanelAction.show),
        )
        self.adjust(1, 1)


class SharePhoneNumber(ReplyKeyboardBuilder):
    share = "📞 ارسال شماره موبایل"

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=self.share,
            request_contact=True,
        )
        self.button(
            text=base.MainMenu.cancel,
        )
        self.adjust(1, 1)
