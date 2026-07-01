from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.handlers.user import account
from app.utils import settings

from .admin import AdminPanel, AdminPanelAction

USERNAME_GENERATORS = {
    settings.UsernameGenerators.randomized: "رندوم",
    settings.UsernameGenerators.incremental: "ترتیبی",
}


class SettingsActions(str, Enum):
    flip_access_only = "access_only"
    flip_referral_system = "referral_system"
    flip_phone_number_verify = "phone_number_verify"

    flip_reset_password_button = "reset_pass_button"

    flip_show_connect_links_button = "connect_links_btn"
    flip_show_test_service_in_menu = "test_in_menu"
    cycle_disable_users_role = "cycle_dis_usrole"
    cycle_username_generator = "cycle_user_gen"

    texts = "texts"
    charge_texts = "charge_texts"
    card_to_card = "card_to_card"
    nowpayments = "nowpayments"
    perfectmoney = "perfectmoney"
    pay_buttons = "pay_buttons"
    payping = "payping"
    aqaye_pardakht = "aqaye_pardakht"
    eswap = "eswap"
    swapino = "swapino"

    misc = "misc"
    reports = "reports"


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="setngs"):
        action: SettingsActions | str
        confirmed: bool = False

    def __init__(self, _settings: "settings.Settings", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"دسترسی فقط به دعوت شدگان: {'✅' if _settings.access_only else '❌'}",
            callback_data=self.Callback(action=SettingsActions.flip_access_only),
        )
        self.button(
            text=f"سیستم زیرمجموعه گیری: {'✅' if _settings.referral_system else '❌'}",
            callback_data=self.Callback(action=SettingsActions.flip_referral_system),
        )
        self.button(
            text=f"تأیید شماره موبایل: {'✅' if _settings.phone_number_verify else '❌'}",
            callback_data=self.Callback(
                action=SettingsActions.flip_phone_number_verify
            ),
        )

        self.button(
            text=f"نمایش دکمه تغییر پسوورد: {'✅' if _settings.reset_password_button else '❌'}",
            callback_data=self.Callback(
                action=SettingsActions.flip_reset_password_button
            ),
        )
        self.button(
            text=f"نمایش دکمه دریافت لینک‌های اتصال: {'✅' if _settings.show_connect_links_button else '❌'}",
            callback_data=self.Callback(
                action=SettingsActions.flip_show_connect_links_button
            ),
        )

        self.button(
            text=f"نمایش سرویس تست در منو: {'✅' if _settings.show_test_service_in_menu else '❌'}",
            callback_data=self.Callback(
                action=SettingsActions.flip_show_test_service_in_menu
            ),
        )
        self.button(
            text=f"سطح دسترسی غیرفعال‌سازی اشتراک: {account.ACCOUNT_TYPE.get(_settings.disable_users_role.name)}",
            callback_data=self.Callback(
                action=SettingsActions.cycle_disable_users_role
            ),
        )

        self.button(
            text=f"نحوه انتخاب نام اشتراک: {USERNAME_GENERATORS.get(_settings.username_generator)}",
            callback_data=self.Callback(
                action=SettingsActions.cycle_username_generator
            ),
        )
        for pb, pk in _settings.payment_plugins().items():
            _s = getattr(_settings, pk)
            self.button(
                text=f"تنظیمات {pb} {'✅' if _s.enabled else '❌'}",
                callback_data=f"pm:settings:{pb}",
            )

        self.button(
            text="تنظیمات دکمه‌های مبالغ پرداختی",
            callback_data=self.Callback(action=SettingsActions.pay_buttons),
        )
        self.button(
            text=f"گروه گزارشات (تاپیک‌ها) {'✅' if _settings.reports_group_id else '❌'}",
            callback_data=self.Callback(action=SettingsActions.reports),
        )
        self.button(
            text="تنظیمات دیگر",
            callback_data=self.Callback(action=SettingsActions.misc),
        )
        self.button(
            text="تنظیمات جواب‌های ربات",
            callback_data=self.Callback(action=SettingsActions.texts),
        )

        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.panel),
        )
        self.adjust(1, 1)


class MSettingsActions(str, Enum):
    edit_minimum_pay_amount = "min_pay_amount"
    edit_default_username_prefix = "username_prefix"
    edit_default_daily_test_services = "daily_test_services"
    edit_payments_discount_on = "discount_on"
    edit_payments_discount_on_percent = "discount_on_percent"
    edit_on_hold_timeout_seconds = "on_hold_timeout_seconds"
    edit_delete_expired_users_after_days = "delete_expired_users_after"
    edit_transaction_logs = "trx_logs"
    edit_orders_logs = "ords_logs"
    edit_referral_discount_percent = "ref_discount_percent"
    edit_cancel_payback_fee = "cancel_payback_fee"
    edit_cancel_payback_days = "cancel_payback_days"
    edit_remind_invoices_each_n_days = "invocie_reminder_days"
    edit_remind_invoices_after_amount = "invoice_reminder_amount"

    edit_marzban_webhook_secret = "marzban_wh_secret"
    edit_force_join_chats = "fj_chats"

    test_perfectmoney = "test_perfectmoney"


class MSettings(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="mstrngss"):
        action: MSettingsActions
        confirmed: bool = False


class SettingsMisc(MSettings):
    def __init__(self, _settings: settings.Settings, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="ویرایش پیشوند پروکسی‌ها",
            callback_data=self.Callback(
                action=MSettingsActions.edit_default_username_prefix
            ),
        )
        self.button(
            text="ویرایش تعداد سرویس‌های تست روزانه",
            callback_data=self.Callback(
                action=MSettingsActions.edit_default_daily_test_services
            ),
        )
        self.button(
            text="ویرایش مدت زمان مجاز شروع از اولین اتصال",
            callback_data=self.Callback(
                action=MSettingsActions.edit_on_hold_timeout_seconds,
            ),
        )
        self.button(
            text="ویرایش حذف خودکار اشتراک‌های منقضی شده",
            callback_data=self.Callback(
                action=MSettingsActions.edit_delete_expired_users_after_days,
            ),
        )
        self.button(
            text="ویرایش لاگ تراکنش‌ها",
            callback_data=self.Callback(action=MSettingsActions.edit_transaction_logs),
        )
        self.button(
            text="ویرایش لاگ سفارشات",
            callback_data=self.Callback(action=MSettingsActions.edit_orders_logs),
        )
        self.button(
            text="ویرایش درصد تخفیف دعوت",
            callback_data=self.Callback(
                action=MSettingsActions.edit_referral_discount_percent
            ),
        )
        self.button(
            text="ویرایش کارمزد لغو اشتراک",
            callback_data=self.Callback(
                action=MSettingsActions.edit_cancel_payback_fee,
            ),
        )
        self.button(
            text="ویرایش تعداد روز برای لغو اشتراک",
            callback_data=self.Callback(
                action=MSettingsActions.edit_cancel_payback_days,
            ),
        )
        self.button(
            text="ویرایش 'Marzban Webhook secret'",
            callback_data=self.Callback(
                action=MSettingsActions.edit_marzban_webhook_secret
            ),
        )
        self.button(
            text="ویرایش کانال‌های عضویت اجباری",
            callback_data=self.Callback(action=MSettingsActions.edit_force_join_chats),
        )

        self.button(
            text="بدهکاری هر چند روز یادآوری شود؟",
            callback_data=self.Callback(
                action=MSettingsActions.edit_remind_invoices_each_n_days
            ),
        )
        self.button(
            text="بدهکاری بعد از چه مبلغی یادآوری شود؟",
            callback_data=self.Callback(
                action=MSettingsActions.edit_remind_invoices_after_amount
            ),
        )

        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1, 1)


class SettingsTextsActions(str, Enum):
    start = "start"
    main_menu = "main_menu"
    force_join = "force_join"
    purchase = "purchase"
    support = "support"
    help = "help"
    command_not_found = "command_not_found"
    proxy_help = "proxy_help"
    referral_banner_text = "referral_banner_text"
    charge = "charge"
    verify_phone_number = "verify_phone_number"


class SettingsTexts(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="stxts"):
        field: SettingsTextsActions

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="متن‌های اصلی ربات👇",
            callback_data="ph",
        )
        self.button(
            text="دستور /start",
            callback_data=self.Callback(field=SettingsTextsActions.start),
        )
        self.button(
            text="دستور /menu",
            callback_data=self.Callback(field=SettingsTextsActions.main_menu),
        )
        self.button(
            text="پیام عضویت اجباری",
            callback_data=self.Callback(field=SettingsTextsActions.force_join),
        )
        self.button(
            text="دکمه «خرید اشتراک»",
            callback_data=self.Callback(field=SettingsTextsActions.purchase),
        )
        self.button(
            text="دکمه «پشتیبانی»",
            callback_data=self.Callback(field=SettingsTextsActions.support),
        )
        self.button(
            text="دکمه «راهنما»",
            callback_data=self.Callback(field=SettingsTextsActions.help),
        )
        self.button(
            text="متن دستور اشتباه",
            callback_data=self.Callback(field=SettingsTextsActions.command_not_found),
        )
        self.button(
            text="راهنمای صفحه اطلاعات اشتراک",
            callback_data=self.Callback(field=SettingsTextsActions.proxy_help),
        )
        self.button(
            text="بنر زیرمجموعه گیری",
            callback_data=self.Callback(
                field=SettingsTextsActions.referral_banner_text
            ),
        )
        self.button(
            text="دکمه «شارژ حساب»",
            callback_data=self.Callback(field=SettingsTextsActions.charge),
        )
        self.button(
            text="متن «تأیید شماره موبایل»",
            callback_data=self.Callback(field=SettingsTextsActions.verify_phone_number),
        )

        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1, 1)


class SettingsTextsEdit(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="edtstxt"):
        field: SettingsTextsActions
        action: Literal["edit", "reset"]
        confirmed: bool = False

    def __init__(
        self,
        field: SettingsTextsActions,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="ویرایش", callback_data=self.Callback(field=field, action="edit")
        )
        self.button(
            text="Reset", callback_data=self.Callback(field=field, action="reset")
        )

        self.button(
            text="برگشت",
            callback_data=SettingsKeyboard.Callback(action=SettingsActions.texts),
        )
        self.adjust(1, 1, 1)


class ConfirmKeyboard(InlineKeyboardBuilder):
    def __init__(
        self,
        data: CallbackData,
        back_to: CallbackData,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=data,
        )

        self.button(
            text="لغو",
            callback_data=back_to,
        )

        self.adjust(1, 1)


class PayAmountSettingActions(str, Enum):
    reset = "reset"
    edit_amounts = "edit_amounts"


class PayAmountSetting(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slcamsett"):
        action: PayAmountSettingActions
        confirmed: bool = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _settings = settings.get_settings()
        amount_list = _settings.charge_amount_list
        orders = _settings.charge_amount_orders
        payments_discount_on = 200_000
        payments_discount_on_percent = 10
        for amount in amount_list:
            free = int(
                0
                if (not payments_discount_on) or (amount < payments_discount_on)
                else amount * (payments_discount_on_percent / 100)
            )
            self.button(
                text=(
                    f"{amount:,} تومان"
                    if not free
                    else f"{free:,} 🔥 + {amount:,} تومان"
                ),
                callback_data="ph",
            )
        self.button(
            text="تنظیمات 👇🏻",
            callback_data="ph",
        )
        self.button(
            text="تغییر مقادیر دکمه‌ها",
            callback_data=self.Callback(action=PayAmountSettingActions.edit_amounts),
        )
        self.button(
            text="بازگشت به تنظیمات پیشفرض",
            callback_data=self.Callback(action=PayAmountSettingActions.reset),
        )

        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        while sum(orders) > len(amount_list):
            if orders[-1] <= 1:
                orders.pop()
            else:
                orders[-1] -= 1

        self.adjust(*orders, 1, 1, 1, 1)


class ConfirmSettings(InlineKeyboardBuilder):
    def __init__(
        self,
        action: SettingsActions,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=SettingsKeyboard.Callback(action=action, confirmed=True),
        )

        self.button(
            text="لغو",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )

        self.adjust(1, 1)


class ConfirmMSettings(InlineKeyboardBuilder):
    def __init__(
        self,
        action: SettingsActions,
        back_to: CallbackData,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=MSettings.Callback(action=action, confirmed=True),
        )

        self.button(
            text="لغو",
            callback_data=back_to,
        )

        self.adjust(1, 1)


class ConfirmPayAmountSettings(InlineKeyboardBuilder):
    def __init__(
        self,
        action: PayAmountSettingActions,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=PayAmountSetting.Callback(action=action, confirmed=True),
        )

        self.button(
            text="لغو",
            callback_data=SettingsKeyboard.Callback(action=SettingsActions.pay_buttons),
        )

        self.adjust(1, 1)


class ReportsSettingsActions(str, Enum):
    set_group = "set_group"
    unset_group = "unset_group"
    toggle_topic = "toggle_topic"
    edit_backup_interval = "backup_interval"
    toggle_nightly = "toggle_nightly"


class ReportsSettings(InlineKeyboardBuilder):
    """Topics-group reporting menu (app/utils/reports.py)."""

    class Callback(CallbackData, prefix="rptstg"):
        action: ReportsSettingsActions
        topic: str = ""
        confirmed: bool = False

    def __init__(self, _settings: "settings.Settings", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from app.utils.reports import TOPIC_TITLES, ReportTopic

        if not _settings.reports_group_id:
            self.button(
                text="🧩 اتصال گروه گزارشات",
                callback_data=self.Callback(action=ReportsSettingsActions.set_group),
            )
        else:
            disabled = _settings.reports_disabled_topics or []
            for topic in ReportTopic:
                self.button(
                    text=f"{TOPIC_TITLES[topic]} {'✅' if topic.value not in disabled else '❌'}",
                    callback_data=self.Callback(
                        action=ReportsSettingsActions.toggle_topic, topic=topic.value
                    ),
                )
            self.button(
                text=f"🌙 گزارش شبانه: {'✅' if _settings.nightly_report_enabled else '❌'}",
                callback_data=self.Callback(
                    action=ReportsSettingsActions.toggle_nightly
                ),
            )
            self.button(
                text=f"🤖 بازه بکاپ: {f'هر {_settings.backup_interval_hours} ساعت' if _settings.backup_interval_hours else 'خاموش'}",
                callback_data=self.Callback(
                    action=ReportsSettingsActions.edit_backup_interval
                ),
            )
            self.button(
                text="🔁 تغییر گروه",
                callback_data=self.Callback(action=ReportsSettingsActions.set_group),
            )
            self.button(
                text="🗑 قطع اتصال گروه",
                callback_data=self.Callback(action=ReportsSettingsActions.unset_group),
            )

        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1)


class ReportsConfirm(InlineKeyboardBuilder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=ReportsSettings.Callback(
                action=ReportsSettingsActions.unset_group, confirmed=True
            ),
        )
        self.button(
            text="لغو",
            callback_data=SettingsKeyboard.Callback(action=SettingsActions.reports),
        )
        self.adjust(1, 1)
