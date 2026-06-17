from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.admin import admin
from app.keyboards.user import proxy
from app.models.user import Transaction, User

ACCOUNT_TYPE = {
    "user": "کاربر معمولی",
    "reseller": "فروشنده",
    "admin": "ادمین",
    "super_user": "ادمین اصلی",
}


class UsersActions(str, Enum):
    show = "show"
    search = "search"


class Users(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="adusrss"):
        action: UsersActions
        current_page: int = 0
        search_text: str | None = None

    def __init__(
        self,
        users: list[User],
        count: int,
        current_page: int = 0,
        next_page: bool = False,
        prev_page: bool = False,
        search_text: str = None,
        *args,
        **kwargs,
    ) -> None:
        """proxies should have 'proxy.server' prefetched"""
        super().__init__(*args, **kwargs)
        if current_page == 0:
            if count > 10:
                if search_text:
                    self.button(
                        text=f"🔍 جستجو: {search_text}",
                        callback_data=self.Callback(
                            current_page=current_page,
                            action=UsersActions.search,
                            search_text=search_text,
                        ),
                    )
                else:
                    self.button(
                        text="🔍 جستجو",
                        callback_data=self.Callback(
                            current_page=current_page,
                            action=UsersActions.search,
                            search_text=search_text,
                        ),
                    )
        elif search_text:
            self.button(
                text=f"🔍 جستجو: {search_text}",
                callback_data=self.Callback(
                    current_page=current_page,
                    action=UsersActions.search,
                    search_text=search_text,
                ),
            )
        for user in users:
            self.button(
                text=f"{'✅' if not user.is_blocked else '❌'} {user.custom_name if user.custom_name else user.name} ({f'@{user.username}' if user.username else user.id})",
                callback_data=ManageUser.Callback(
                    user_id=user.id,
                    action=ManageUserAction.info,
                    current_page=current_page,
                    search_text=search_text,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ صفحه قبل",
                callback_data=self.Callback(
                    action=UsersActions.show,
                    current_page=current_page - 1,
                    search_text=search_text,
                ),
            )
        if next_page:
            self.button(
                text="➡️ صفحه بعد",
                callback_data=self.Callback(
                    action=UsersActions.show,
                    current_page=current_page + 1,
                    search_text=search_text,
                ),
            )
        if current_page == 0 and search_text is not None:
            self.button(
                text="♻️ نمایش همه کاربران",
                callback_data=self.Callback(
                    action=UsersActions.show,
                    current_page=current_page,
                ),
            )
        if current_page == 0 and count > 10:
            self.adjust(*[1 for _ in range(14)], 2, 1)
        else:
            self.adjust(*[1 for _ in range(11)], 2, 1)
        self.button(
            text="برگشت به منو اصلی",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.panel
            ),
        )


class ManageUserAction(str, Enum):
    info = "info"
    discount_percent = "discount_percent"
    max_test_services = "max_test_services"
    proxy_prefix = "proxy_prefix"
    block_user = "block_user"
    cycle_role = "cycle_role"
    unblock_user = "unblock_user"
    verify_user = "verify_user"
    unverify_user = "unverify_user"
    postpaid = "postpaid"
    nopostpaid = "nopostpaid"
    card_to_card_auto_accept = "card_to_card_auto"
    max_postpaid_credit = "max_postpaid_credit"
    custom_name = "custom_name"


class ManageUser(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="admmngusr"):
        user_id: int
        action: ManageUserAction

        current_page: int = 0
        search_text: str | None = None

    def __init__(
        self,
        user: User,
        current_page: int = 0,
        search_text: str = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"سطح کاربری: {ACCOUNT_TYPE.get(user.role.name)}",
            callback_data=self.Callback(
                user_id=user.id,
                current_page=current_page,
                action=ManageUserAction.cycle_role,
            ),
        )
        self.button(
            text="پروکسی‌ها",
            callback_data=proxy.Proxies.Callback(
                user_id=user.id,
                action=proxy.ProxiesActions.show,
                current_page=0,
            ),
        )
        self.button(
            text="تراکنش‌ها",
            callback_data=ManageTrx.Callback(
                user_id=user.id,
                action=ManageTrxAction.show_all,
            ),
        )
        self.button(
            text="درصد تخفیف",
            callback_data=self.Callback(
                user_id=user.id,
                current_page=current_page,
                action=ManageUserAction.discount_percent,
            ),
        )
        self.button(
            text="پیشوند پروکسی‌ها",
            callback_data=self.Callback(
                user_id=user.id,
                current_page=current_page,
                action=ManageUserAction.proxy_prefix,
            ),
        )
        if user.role == User.Role.reseller:
            self.button(
                text="تعداد دریافت سرویس‌‌های تست",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.max_test_services,
                ),
            )
        if user.is_blocked:
            self.button(
                text="رفع مسدودی",
                callback_data=self.Callback(
                    current_page=current_page,
                    user_id=user.id,
                    action=ManageUserAction.unblock_user,
                ),
            )
        else:
            self.button(
                text="مسدود کردن",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.block_user,
                ),
            )
        if user.is_verified:
            self.button(
                text="کاربر تأیید شده ✅",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.unverify_user,
                ),
            )
        else:
            self.button(
                text="کاربر تأیید نشده ❌",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.verify_user,
                ),
            )
        self.button(
            text=f"{'✅' if user.card_to_card_auto_accept else '❌'} تأیید خودکار رسید کارت به کارت",
            callback_data=self.Callback(
                user_id=user.id,
                current_page=current_page,
                action=ManageUserAction.card_to_card_auto_accept,
            ),
        )
        if user.is_postpaid:
            self.button(
                text="پس‌پرداخت نباشد",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.nopostpaid,
                ),
            )
            self.button(
                text="تنظیم حداکثر اعتبار در دسترس",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.max_postpaid_credit,
                ),
            )
        else:
            self.button(
                text="تبدیل به پس‌پرداخت",
                callback_data=self.Callback(
                    user_id=user.id,
                    current_page=current_page,
                    action=ManageUserAction.postpaid,
                ),
            )
        self.button(
            text="تنظیم نام مستعار",
            callback_data=self.Callback(
                user_id=user.id,
                current_page=current_page,
                action=ManageUserAction.custom_name,
            ),
        )
        self.button(
            text="نمایش لیست همه کاربران",
            callback_data=Users.Callback(
                action=UsersActions.show,
                current_page=current_page,
                search_text=search_text,
            ),
        )
        self.adjust(1, 1)


class ManageTrxAction(str, Enum):
    show = "show"
    show_all = "show_all"


TRX_STATUS = {
    Transaction.Status.waiting: "⏳",
    Transaction.Status.failed: "❌",
    Transaction.Status.canceled: "⛔️",
    Transaction.Status.partially_paid: "🪫",
    Transaction.Status.rejected: "🚫",
    Transaction.Status.finished: "✅",
    Transaction.Status.confirming: "♻️",
    Transaction.Status.sending: "☑️",
}


class ManageTrx(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="admpmntsusr"):
        user_id: int
        trx_id: int = 0
        action: ManageTrxAction
        current_page: int = 0

    def __init__(
        self,
        user_id: int,
        transactions: list[Transaction],
        count: int,
        current_page: int = 0,
        next_page: bool = False,
        prev_page: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for transaction in transactions:
            self.button(
                text=f"{transaction.id}: {TRX_STATUS.get(transaction.status, '➖')} | {transaction.type.name} | {transaction.amount - transaction.amount_free_given:,}",
                callback_data=self.Callback(
                    user_id=user_id,
                    trx_id=transaction.id,
                    action=ManageTrxAction.show,
                    current_page=current_page,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ صفحه قبل",
                callback_data=self.Callback(
                    user_id=user_id,
                    action=ManageTrxAction.show_all,
                    current_page=current_page - 1,
                ),
            )
        if next_page:
            self.button(
                text="➡️ صفحه بعد",
                callback_data=self.Callback(
                    user_id=user_id,
                    action=ManageTrxAction.show_all,
                    current_page=current_page + 1,
                ),
            )
        self.button(
            text="🔙 برگشت",
            callback_data=ManageUser.Callback(
                user_id=user_id,
                action=ManageUserAction.info,
            ),
        )
        self.adjust(
            *[1 for _ in range(count - 1)], 2 if all([next_page, prev_page]) else 1, 1
        )
