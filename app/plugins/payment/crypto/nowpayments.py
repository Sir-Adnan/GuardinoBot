# ruff: noqa: E402


SETTINGS_KEY_PREFIX = "nowpayments.io"


from enum import Enum
from typing import Any, Callable

import config
from app.plugins.payment.utils import BaseSettings, BaseTexts
from app.utils.values import TextValue, format_number


class Fields(str, Enum):
    enabled = "enabled"
    min_pay_amount = "min_pay_amount"
    free_after = "free_after"
    free_after_percent = "free_after_percent"
    menu_title = "menu_title"

    api_key = "api_key"
    ipn_secret_key = "ipn_secret_key"

    text_choose_amount = "text_choose_amount"
    text_show_invoice = "text_show_invoice"


class Settings(BaseSettings):
    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "💸 ارز دیجیتال"

    api_key: str | None = config.NP_API_KEY
    ipn_secret_key: str | None = config.NP_IPN_SECRET_KEY
    rate_provider: str = config.PAYMENT_RATE_PROVIDER
    rate_cache_seconds: int = config.PAYMENT_RATE_CACHE_SECONDS
    usdt_margin_percent: str = config.PAYMENT_USDT_MARGIN_PERCENT
    manual_usdt_toman_rate: str | None = config.MANUAL_USDT_TOMAN_RATE


class ChooseAmountText(TextValue):
    value: str = """
✔️ شما در حال افزایش اعتبار با {PAYMENT_PROVIDER_TITLE} هستید!

❗️اگر اشتباه وارد این بخش شدید دکمه «برگشت» را کلیک کنید
~~~~~~~~~~~~~~~~~~~~~~~~
❗️ اگر با نحوه پرداخت به وسیله ارز دیجیتال آشنایی ندارید، حتما روی لینک زیر کلیک کنید و آموزش رو مشاهده کنید:
❔ <a href='https://t.me'>آموزش شارژ حساب با ارز دیجیتال</a>
~~~~~~~~~~~~~~~~~~~~~~~~
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": str,
        "USDT_RATE": float,
        "MINIMUM_PAY_AMOUNT": int,
    }


class ShowInvoiceText(TextValue):
    value: str = """
🧾 <b>فاکتور پرداخت ارزی</b>

مبلغ سفارش: <b>{AMOUNT_TOMAN}</b> تومان
کد پیگیری: <code>{TRACKING_CODE}</code>
شناسه درگاه: <code>{INVOICE_ID}</code>

مبلغ مبنا: <b>{AMOUNT_DOLLARS}</b> USDT

در صفحه پرداخت می‌توانید ارز موردنظر را انتخاب کنید. پس از تأیید شبکه، پرداخت به‌صورت خودکار ثبت می‌شود.
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": lambda v: v,
        "USDT_RATE": format_number,
        "MINIMUM_PAY_AMOUNT": format_number,
        "TRANSACTION_ID": format_number,
        "AMOUNT_TOMAN": format_number,
        # AMOUNT_DOLLARS is a fractional USDT value rendered via _format_decimal
        # (a pre-formatted string) — format_number's `{:,}` blows up on strings.
        "AMOUNT_DOLLARS": str,
        "AMOUNT_RIAL": format_number,
        "TRACKING_CODE": str,
        "INVOICE_ID": str,
    }


class Texts(BaseTexts):
    choose_amount: ChooseAmountText = ChooseAmountText()
    show_invoice: ShowInvoiceText = ShowInvoiceText()


from typing import Literal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

from app.logger import get_logger
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.premium import premium_button
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.utils import settings, texts
from app.utils.filters import IsSuperUser
from app.utils.values import admin_edit_texts_format, check_texts

from .clients import NowPaymentsAPI, NowPaymentsError
from .nowpayments_service import (
    check_nowpayments_transaction,
)
from .rates import PaymentRateError, calculate_payable_usdt, get_usdt_toman_rate

router = Router(name="payment/nowpayments")
logger = get_logger("payment/nowpayments")


# # Admin settings Start
cancel_admin_form = CancelFormAdmin().as_markup(
    resize_keyboard=True, one_time_only=True
)


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="set_nowpayments"):
        field: Fields
        confirmed: bool = False

    def __init__(self, settings: Settings, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'فعال ✅' if settings.enabled else 'غیرفعال ❌'}",
            callback_data=self.Callback(field=Fields.enabled),
        )
        self.button(
            text="ویرایش 'API Key'",
            callback_data=self.Callback(field=Fields.api_key),
        )
        self.button(
            text="ویرایش 'IPN secret key'",
            callback_data=self.Callback(field=Fields.ipn_secret_key),
        )
        self.button(
            text="ویرایش 'حداقل مبلغ قابل پرداخت'",
            callback_data=self.Callback(field=Fields.min_pay_amount),
        )
        self.button(
            text="ویرایش 'نام مستعار'",
            callback_data=self.Callback(field=Fields.menu_title),
        )
        self.button(
            text="ویرایش متن 'انتخاب مبلغ'",
            callback_data=self.Callback(field=Fields.text_choose_amount),
        )
        self.button(
            text="ویرایش متن 'نمایش فاکتور'",
            callback_data=self.Callback(field=Fields.text_show_invoice),
        )
        self.button(
            text="ویرایش حداقل مبلغ برای اعتبار هدیه",
            callback_data=self.Callback(
                field=Fields.free_after,
            ),
        )
        self.button(
            text="ویرایش درصد اعتبار هدیه",
            callback_data=self.Callback(
                field=Fields.free_after_percent,
            ),
        )
        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1, 1)


class TextsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="txt_nowpayments"):
        action: Literal["edit", "reset"]
        field: Fields
        confirmed: bool = False

    def __init__(self, field: Fields, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="ویرایش", callback_data=self.Callback(action="edit", field=field)
        )
        self.button(
            text="Reset", callback_data=self.Callback(action="reset", field=field)
        )

        self.button(text="برگشت", callback_data=f"pm:settings:{SETTINGS_KEY_PREFIX}")
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


class NowPaymentsInvoiceAction(CallbackData, prefix="npayact"):
    action: Literal["check", "cancel"]
    transaction_id: int


class PayUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, transaction_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="💳 پرداخت آنلاین",
                key="nowpayments_pay_online",
                url=url,
            )
        )
        self.add(
            premium_button(
                text="🔄 بررسی وضعیت پرداخت",
                key="nowpayments_check_payment",
                callback_data=NowPaymentsInvoiceAction(
                    action="check", transaction_id=transaction_id
                ),
            )
        )
        self.add(
            premium_button(
                text="❌ لغو فاکتور",
                key="nowpayments_cancel_invoice",
                callback_data=NowPaymentsInvoiceAction(
                    action="cancel", transaction_id=transaction_id
                ),
            )
        )
        self.adjust(1)


class NowpaymentsEditForm(StatesGroup):
    api_key = State()
    ipn_secret_key = State()
    menu_title = State()
    min_pay_amount = State()

    free_after = State()
    free_after_percent = State()

    text_choose_amount = State()
    text_show_invoice = State()


class NowpaymentsCustomAmountForm(StatesGroup):
    method = State()
    amount = State()


def _format_decimal(value) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _direct_invoice_type(mode: str | None):
    if mode == "renew":
        return Invoice.Type.renew_now
    if mode == "reserve":
        return Invoice.Type.renew_reserve
    return Invoice.Type.purchase


def _mask_secret(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return "ثبت‌نشده"
    return ("•" * max(0, len(text) - 4)) + text[-4:]


@router.message(
    StateFilter(NowpaymentsEditForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
    ~CommandStart(),
    ~Command("menu"),
)
@router.callback_query(
    F.data == f"pm:settings:{SETTINGS_KEY_PREFIX}",
    IsSuperUser(),
)
async def show_settings(
    qmsg: CallbackQuery | Message, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    _settings = settings.get_settings().payment_nowpayments
    text = f"""
API Key: <code>{_mask_secret(_settings.api_key)}</code>
IPN Secret key: <code>{_mask_secret(_settings.ipn_secret_key)}</code>

نام مستعار: <b>{_settings.menu_title}</b>

حداقل مبلغ قابل پرداخت: <code>{_settings.min_pay_amount}</code>
منبع نرخ: <code>{_settings.rate_provider or 'nobitex'}</code>
مارجین تتر: <code>{_settings.usdt_margin_percent}</code>٪

اعتبار هدیه برای مبلغ بیشتر از: <code>{_settings.free_after:,}</code>
درصد اعتبار هدیه: <code>{_settings.free_after_percent} %</code>

راهنما: https://t.me/c/1921580752
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text, reply_markup=SettingsKeyboard(settings=_settings).as_markup()
        )
    return await qmsg.reply(
        text=text, reply_markup=SettingsKeyboard(settings=_settings).as_markup()
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.enabled),
    IsSuperUser(),
)
async def edit_settings(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_nowpayments
    if _settings.enabled:
        _settings.enabled = False
        text = "درگاه nowpayments غیرفعال شد!"
    else:
        _settings.enabled = True
        text = "درگاه nowpayments فعال شد!"
    await settings.Settings.update(payment_nowpayments=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.field.in_([Fields.text_choose_amount, Fields.text_show_invoice])
    ),
    IsSuperUser(),
)
async def edit_settings_texts(
    qmsg: CallbackQuery | Message, user: User, callback_data: SettingsKeyboard.Callback
):
    _texts = texts.get_texts()
    ed_text = None
    if callback_data.field == Fields.text_choose_amount:
        ed_text = _texts.payment_nowpayments.choose_amount
    elif callback_data.field == Fields.text_show_invoice:
        ed_text = _texts.payment_nowpayments.show_invoice
    else:
        text = f"متن برای {callback_data.field.name} تعریف نشده است!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                text=text,
                show_alert=True,
            )
        return await qmsg.answer(text=text)

    text = admin_edit_texts_format(ed_text=ed_text, field=callback_data.field.name)

    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text,
            reply_markup=TextsKeyboard(field=callback_data.field).as_markup(),
            disable_web_page_preview=True,
        )
    await qmsg.answer(
        text=text,
        reply_markup=TextsKeyboard(field=callback_data.field).as_markup(),
        disable_web_page_preview=True,
    )


@router.callback_query(
    TextsKeyboard.Callback.filter(F.action == "reset"),
    IsSuperUser(),
)
async def texts_reset(
    query: CallbackQuery,
    user: User,
    callback_data: TextsKeyboard.Callback,
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "آیا مطمئن هستید که میخواهید این متن را به مقدار پیشفرض بازنشانی کنید؟",
            reply_markup=ConfirmKeyboard(
                data=TextsKeyboard.Callback(
                    action="reset", field=callback_data.field, confirmed=True
                ),
                back_to=SettingsKeyboard.Callback(field=callback_data.field),
            ).as_markup(),
        )
    _texts = texts.get_texts().payment_nowpayments
    if callback_data.field == Fields.text_choose_amount:
        _texts.choose_amount = ChooseAmountText()
    elif callback_data.field == Fields.text_show_invoice:
        _texts.show_invoice = ShowInvoiceText()
    else:
        return await query.answer(
            f"بازنشانی متن برای {callback_data.field.name} تعریف نشده است!"
        )
    await texts.Texts.update(payment_nowpayments=_texts)
    await texts.reload_texts()

    await query.answer(
        f"{callback_data.field.name} به مقدار پیشفرض بازنشانی شد!", show_alert=True
    )
    try:
        await edit_settings_texts(query, user, callback_data)
    except TelegramBadRequest:
        pass


@router.callback_query(
    TextsKeyboard.Callback.filter(F.action == "edit"),
    IsSuperUser(),
)
async def texts_edit(
    query: CallbackQuery,
    user: User,
    callback_data: TextsKeyboard.Callback,
    state: FSMContext,
):
    if callback_data.field == Fields.text_choose_amount:
        await state.set_state(NowpaymentsEditForm.text_choose_amount)
    elif callback_data.field == Fields.text_show_invoice:
        await state.set_state(NowpaymentsEditForm.text_show_invoice)
    else:
        return await query.answer(
            f"ویرایش متن برای {callback_data.field.name} تعریف نشده است!"
        )
    text = f"""
متن مورد نظر برای قسمت {callback_data.field.name} را ارسال کنید: 
(ربات جهت تست یک بار متن را برای خود شما ارسال ‌می‌کند و اگر موفقیت آمیز بود، متن زخیره می‌شود.)
"""
    await query.message.reply(text=text, reply_markup=cancel_admin_form)


@router.message(
    NowpaymentsEditForm.text_choose_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts().payment_nowpayments

    if not await check_texts(_texts.choose_amount, message):
        return
    _texts.choose_amount = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_nowpayments=_texts)
    await texts.reload_texts()
    text = f"""
متن choose_amount با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsKeyboard.Callback(field=Fields.text_choose_amount),
    )


@router.message(
    NowpaymentsEditForm.text_show_invoice,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts().payment_nowpayments

    if not await check_texts(_texts.show_invoice, message):
        return
    _texts.show_invoice = ShowInvoiceText(value=message.text)
    await texts.Texts.update(payment_nowpayments=_texts)
    await texts.reload_texts()
    text = f"""
متن show_invoice با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsKeyboard.Callback(field=Fields.text_show_invoice),
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings().payment_nowpayments
    if callback_data.field == Fields.api_key:
        text = "مقدار جدید API key را وارد کنید: (برای عدم تنظیم <code>0</code> را وارد کنید)"
        await state.set_state(NowpaymentsEditForm.api_key)

    elif callback_data.field == Fields.ipn_secret_key:
        text = "مقدار جدید Secret Key را وارد کنید:"
        await state.set_state(NowpaymentsEditForm.ipn_secret_key)

    elif callback_data.field == Fields.min_pay_amount:
        text = "مقدار جدید حداقل مبلغ قابل پرداخت را به تومان وارد کنید:"
        await state.set_state(NowpaymentsEditForm.min_pay_amount)

    elif callback_data.field == Fields.menu_title:
        text = "مقدار جدید نام مستعار را وارد کنید:"
        await state.set_state(NowpaymentsEditForm.menu_title)

    elif callback_data.field == Fields.free_after:
        text = f"تراکنش‌ها از چه مبلغی به بعد شامل {_settings.free_after_percent} درصد اعتبار هدیه شوند؟ برای غیرفعال سازی 0 را وارد کنید:"
        await state.set_state(NowpaymentsEditForm.free_after)

    elif callback_data.field == Fields.free_after_percent:
        if not _settings.free_after:
            return await query.answer(
                "ابتدا اعتبار هدیه را فعال کرده و سپس درصد را تنظیم کنید!"
            )
        text = f"تراکنش‌های بیشتر از {_settings.free_after:,} شامل چند درصد اعتبار هدیه شوند؟"
        await state.set_state(NowpaymentsEditForm.free_after_percent)
    else:
        return await query.answer(
            f"تنظیمات برای {callback_data.field.value} تعریف نشده است!", show_alert=True
        )
    await query.message.reply(
        text=text,
        reply_markup=cancel_admin_form,
    )


@router.message(
    NowpaymentsEditForm.api_key,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_api_key(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    api_key = message.text.strip()
    if api_key == "0":
        api_key = None
    else:
        try:
            await NowPaymentsAPI.get_available_currencies(api_key=api_key)
        except NowPaymentsError as exc:
            text = f"""
error: {exc}

Could not verify nowpayments.io API key! try again:
"""
            await message.reply(text)
            raise exc
    origv = _settings.api_key
    _settings.api_key = api_key
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{_mask_secret(origv)}</code>
مقدار جدید: <code>{_mask_secret(api_key)}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    NowpaymentsEditForm.ipn_secret_key,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_ipn_secret_key(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    ipn_secret_key = message.text.strip()
    if ipn_secret_key == "0":
        ipn_secret_key = None
    origv = _settings.ipn_secret_key
    _settings.ipn_secret_key = ipn_secret_key
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{_mask_secret(origv)}</code>
مقدار جدید: <code>{_mask_secret(ipn_secret_key)}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    NowpaymentsEditForm.menu_title,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_menu_title(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    menu_title = message.text.strip().replace("\n", " ")
    origv = _settings.menu_title
    _settings.menu_title = menu_title
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{menu_title}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    NowpaymentsEditForm.min_pay_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_min_pay_amount(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    try:
        min_pay_amount = int(message.text)
    except ValueError:
        return await message.reply(
            f"{message.text} مقداری نامعتبر است! لطفا مقداری عددی وارد کنید:"
        )
    origv = _settings.min_pay_amount
    _settings.min_pay_amount = min_pay_amount
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{min_pay_amount}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    NowpaymentsEditForm.free_after,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    free_after = message.text.strip()
    try:
        free_after = int(free_after)
        if free_after < 0:
            raise ValueError()
    except ValueError:
        return message.reply(
            f"{free_after} مقداری نامعتر است! لطفا مقداری عددی و بیشتر از 0 وارد کنید:"
        )
    origv = _settings.free_after
    _settings.free_after = free_after
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{free_after}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    NowpaymentsEditForm.free_after_percent,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after_percent(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_nowpayments
    free_after_percent = message.text.strip()
    try:
        free_after_percent = int(free_after_percent)
    except ValueError:
        return message.reply(
            f"{free_after_percent} مقداری نامعتبر است! لطفا مقداری عددی وارد کنید::"
        )
    if free_after_percent > 100 or free_after_percent < 0:
        return message.reply(
            f"{free_after_percent} مقدار وارد شده باید بین 0 تا 100 باشد:"
        )
    origv = _settings.free_after_percent
    _settings.free_after_percent = free_after_percent
    await settings.Settings.update(payment_nowpayments=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{free_after_percent}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


# # Admin Settings End

# # User handlers Start


@router.message(
    F.text.in_([base.MainMenu.cancel, base.MainMenu.back]),
    ~CommandStart(),
    ~Command("menu"),
    StateFilter(NowpaymentsCustomAmountForm),
)
@router.callback_query(
    payment.ChargePanel.Callback.filter(F.method == SETTINGS_KEY_PREFIX)
)
async def select(qmsg: CallbackQuery | Message, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        text = "🌀 عملیات لغو شد!"
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text)
        else:
            await qmsg.answer(text=text, reply_markup=ReplyKeyboardRemove())
    _settings = settings.get_settings()
    try:
        if (
            not _settings.payment_nowpayments.enabled
            or not await NowPaymentsAPI.status()
        ):
            raise NowPaymentsError()
    except NowPaymentsError:
        text = (
            "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید. (کد ۳۲)",
        )
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                text=text,
                show_alert=True,
            )
        return await qmsg.answer(
            text=text,
        )
    try:
        usdt_rate = await get_usdt_toman_rate(_settings.payment_nowpayments)
        _texts = texts.get_texts().payment_nowpayments
        text = texts.Texts.format(
            _texts.choose_amount,
            PAYMENT_PROVIDER_TITLE=_settings.payment_nowpayments.menu_title,
            USDT_RATE=int(usdt_rate),
            MINIMUM_PAY_AMOUNT=_settings.payment_nowpayments.min_pay_amount,
        )
        markup = payment.SelectPayAmount(
            method=SETTINGS_KEY_PREFIX,
            _settings=_settings,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=markup,
            )
        return await qmsg.answer(
            text,
            reply_markup=markup,
        )
    except PaymentRateError as err:
        text = "📍 خطایی در دریافت نرخ ارز رخ داد! لطفا با پشتیبانی تماس بگیرید."
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(
                text=text,
                show_alert=True,
            )
        else:
            await qmsg.answer(
                text=text,
            )
        raise err


@router.callback_query(
    payment.SelectPayAmount.Callback.filter(
        (F.amount == 0) & (F.method == SETTINGS_KEY_PREFIX)
    )
)
async def custom_amount(
    query: CallbackQuery,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings()
    min_pay_amount, _, _ = payment.get_payment_variables(
        callback_data.method, _settings
    )
    text = f"""
💴 مبلغ مورد نظر برای افزایش اعتبار را وارد کنید: (حداقل {min_pay_amount:,})
"""
    await state.set_state(NowpaymentsCustomAmountForm.amount)
    await state.set_data({"method": callback_data.method})
    await query.message.answer(
        text,
        reply_markup=base.CancelUserForm(cancel=True).as_markup(
            resize_keyboard=True, one_time_keyboard=True
        ),
    )


@router.message(
    ~F.text.in_([CancelFormAdmin.cancel, base.MainMenu.main_menu]),
    ~CommandStart(),
    ~Command("menu"),
    NowpaymentsCustomAmountForm.amount,
)
async def get_custom_amount(message: Message, user: User, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply("❌ لطفا مقداری عددی وارد کنید:")

    _settings = settings.get_settings()
    min_pay_amount, free_after, free_after_percent = payment.get_payment_variables(
        SETTINGS_KEY_PREFIX, _settings
    )
    if amount < min_pay_amount:
        return await message.reply(
            f"❌ لطفا مقداری بیشتر از {min_pay_amount:,} وارد کنید:"
        )

    free = (
        0
        if (not free_after) or (amount < free_after)
        else amount * (free_after_percent / 100)
    )
    await state.clear()
    return await select_amount(
        message,
        user,
        callback_data=payment.SelectPayAmount.Callback(
            amount=amount, free=free, method=SETTINGS_KEY_PREFIX
        ),
    )


@router.callback_query(
    payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX)
)
async def select_amount(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
):
    _settings = settings.get_settings().payment_nowpayments
    if not _settings.enabled:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید.",
                show_alert=True,
            )
        return await qmsg.answer(
            "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید.",
            show_alert=True,
        )
    await qmsg.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        usdt_rate = await get_usdt_toman_rate(_settings)
        payable_usdt = calculate_payable_usdt(
            callback_data.amount, usdt_rate, _settings.usdt_margin_percent
        )
        public_base = config.PUBLIC_BASE_URL
        async with in_transaction():
            transaction = await Transaction.create(
                type=Transaction.PaymentType.crypto,
                status=Transaction.Status.waiting,
                amount=callback_data.amount + callback_data.free,
                amount_free_given=callback_data.free,
                user=user,
            )
            if callback_data.direct_mode is not None:
                await Invoice.create(
                    amount=callback_data.amount,
                    type=_direct_invoice_type(callback_data.direct_mode),
                    is_paid=False,
                    is_draft=True,
                    service_id=callback_data.service_id or None,
                    proxy_id=callback_data.proxy_id or None,
                    user=user,
                    transaction=transaction,
                )
            tracking_code = f"GB-{transaction.id}"
            invoice = await NowPaymentsAPI.create_invoice(
                price_amount=payable_usdt,
                order_id=str(transaction.id),
                order_description=tracking_code,
                ipn_callback_url=f"{public_base}/npipn",
                success_url=f"{public_base}/payments/nowpayments/success",
                cancel_url=f"{public_base}/payments/nowpayments/fail",
                partially_paid_url=f"{public_base}/payments/nowpayments/partial",
            )
            await CryptoPayment.create(
                transaction=transaction,
                provider=CryptoPayment.Provider.nowpayments,
                usdt_rate=int(usdt_rate),
                invoice_id=invoice.id,
                order_id=invoice.order_id,
                price_amount=float(payable_usdt),
                price_currency=invoice.price_currency,
                order_description=tracking_code,
                nowpm_created_at=invoice.created_at,
                nowpm_updated_at=invoice.updated_at,
                payment_status=CryptoPayment.PaymentStatus.waiting,
                extra_data={
                    "invoice_url": invoice.invoice_url,
                    "tracking_code": tracking_code,
                    "invoice_id": invoice.id,
                    "rate": str(usdt_rate),
                    "margin_percent": str(_settings.usdt_margin_percent),
                    "payable_usdt": str(payable_usdt),
                    "raw_create_response": invoice.model_dump(mode="json"),
                    "status_source": "created",
                },
            )
        _texts = texts.get_texts().payment_nowpayments
        text = texts.Texts.format(
            _texts.show_invoice,
            PAYMENT_PROVIDER_TITLE=_settings.menu_title,
            USDT_RATE=int(usdt_rate),
            TRANSACTION_ID=transaction.id,
            AMOUNT_TOMAN=transaction.amount - transaction.amount_free_given,
            AMOUNT_DOLLARS=_format_decimal(payable_usdt),
            TRACKING_CODE=tracking_code,
            INVOICE_ID=invoice.id,
        )
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text=text,
                reply_markup=PayUrl(
                    url=invoice.invoice_url, transaction_id=transaction.id
                ).as_markup(),
            )
        return await qmsg.answer(
            text=text,
            reply_markup=PayUrl(
                url=invoice.invoice_url, transaction_id=transaction.id
            ).as_markup(),
        )
    except NowPaymentsError as err:
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(
                "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید.",
                show_alert=True,
            )
        else:
            await qmsg.answer(
                "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
            )
        raise err
    except PaymentRateError as err:
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(
                "📍 خطایی در دریافت نرخ ارز رخ داد! لطفا با پشتیبانی تماس بگیرید.",
                show_alert=True,
            )
        else:
            await qmsg.answer(
                "📍 خطایی در دریافت نرخ ارز رخ داد! لطفا با پشتیبانی تماس بگیرید."
            )
        raise err
    except Exception as err:  # noqa: BLE001
        logger.exception("nowpayments invoice flow failed")
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(
                "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید.",
                show_alert=True,
            )
        else:
            await qmsg.answer(
                "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
            )
        raise err


@router.callback_query(NowPaymentsInvoiceAction.filter(F.action == "check"))
async def check_invoice(
    query: CallbackQuery,
    user: User,
    callback_data: NowPaymentsInvoiceAction,
):
    transaction = await Transaction.filter(id=callback_data.transaction_id).first()
    if not transaction or transaction.user_id != user.id:
        return await query.answer("فاکتور پیدا نشد.", show_alert=True)
    if transaction.status == Transaction.Status.finished:
        return await query.answer("پرداخت قبلا تایید شده است ✅", show_alert=True)
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.nowpayments:
        return await query.answer("فاکتور پیدا نشد.", show_alert=True)
    try:
        result = await check_nowpayments_transaction(
            transaction, source="manual_check"
        )
    except NowPaymentsError:
        return await query.answer(
            "امکان بررسی وضعیت پرداخت در این لحظه وجود ندارد.", show_alert=True
        )

    if result["result"] in {"completed", "already_finished"}:
        return await query.answer("پرداخت تایید شد ✅", show_alert=True)
    if result["result"] == "pending":
        return await query.answer(
            "پرداخت هنوز در انتظار تایید شبکه است.", show_alert=True
        )
    if result["result"] == "review":
        return await query.answer(
            "پرداخت نیاز به بررسی پشتیبانی دارد. کد پیگیری را برای پشتیبانی ارسال کنید.",
            show_alert=True,
        )
    if result["result"] == "failed":
        return await query.answer(
            "پرداخت ناموفق، منقضی یا برگشت‌خورده ثبت شده است.", show_alert=True
        )
    if result["result"] == "no_payment":
        return await query.answer(
            "هنوز پرداختی برای این فاکتور در درگاه ثبت نشده است.", show_alert=True
        )
    return await query.answer(
        "وضعیت پرداخت نامشخص است؛ با پشتیبانی تماس بگیرید.", show_alert=True
    )


@router.callback_query(NowPaymentsInvoiceAction.filter(F.action == "cancel"))
async def cancel_invoice(
    query: CallbackQuery,
    user: User,
    callback_data: NowPaymentsInvoiceAction,
):
    transaction = await Transaction.filter(id=callback_data.transaction_id).first()
    if not transaction or transaction.user_id != user.id:
        return await query.answer("فاکتور پیدا نشد.", show_alert=True)
    if transaction.status == Transaction.Status.finished:
        return await query.answer(
            "این فاکتور قبلا پرداخت و تایید شده است.", show_alert=True
        )
    await Transaction.filter(id=transaction.id).update(status=Transaction.Status.canceled)
    await CryptoPayment.filter(transaction_id=transaction.id).update(
        payment_status=CryptoPayment.PaymentStatus.failed,
    )
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    return await query.answer("فاکتور لغو شد.", show_alert=True)
