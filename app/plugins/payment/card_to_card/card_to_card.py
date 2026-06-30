# ruff: noqa: E402

SETTINGS_KEY_PREFIX = "card_to_card"

from enum import Enum
from html import escape
from typing import Any, Callable

from app.plugins.payment.utils import BaseSettings, BaseTexts
from app.utils.values import TextValue, format_card_number, format_number


class Fields(str, Enum):
    enabled = "enabled"
    min_pay_amount = "min_pay_amount"
    free_after = "free_after"
    free_after_percent = "free_after_percent"
    menu_title = "menu_title"
    verify_before_show_card = "verify_before_show_card"

    cards = "cards"

    text_choose_amount = "text_choose_amount"
    text_show_invoice = "text_show_invoice"
    text_not_verified_for_show = "text_not_verified_for_show"


class Settings(BaseSettings):
    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "💳 کارت به کارت"

    verify_before_show_card: bool = False


class ChooseAmountText(TextValue):
    value: str = """
✔️ شما در حال افزایش اعتبار با کارت به کارت هستید!

❗️اگر اشتباه وارد این بخش شدید دکمه «برگشت» را کلیک کنید

✔️ برای ادامه، مبلغ مورد نظر برای افزایش اعتبار رو انتخاب کنید:
‌‌
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": str,
        "MINIMUM_PAY_AMOUNT": int,
    }


class ShowInvoiceText(TextValue):
    value: str = """
✅ فاکتور افزایش اعتبار شما ساخته شد!

💳 شماره فاکتور: {TRANSACTION_ID}
💲مبلغ قابل پرداخت: {AMOUNT_RIAL} ریال
~~~~~~~~~~~~~~~~~~~~~~~~
💳 شماره کارت: <code>{CARD_NUMBER}</code>
👤 صاحب کارت: <b>{CARD_HOLDER}</b>

🔵 برای تأیید پرداخت، عکس رسید خود را ارسال کنید. بعد از پرداخت و تأیید تراکنش، مبلغ مورد نظر به حساب شما اضافه می‌شود!

🔴 برای تأیید سریعتر، مبلغ تراکنش را حتما به صورت کاملا دقیق وارد کنید. در صورت تأیید نشدن به صورت خودکار، رسید خود را به پشتیبانی ارسال کنید.

⚠️ فاکتور پرداخت شما تا ۲۰ دقیقه دیگر معتبر می‌باشد.
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": lambda v: v,
        "MINIMUM_PAY_AMOUNT": format_number,
        "TRANSACTION_ID": format_number,
        "AMOUNT_TOMAN": format_number,
        "AMOUNT_RIAL": format_number,
        "CARD_NUMBER": format_card_number,
        "CARD_HOLDER": lambda v: f"<code>{v}</code>",
    }


class NotVerifiedForShow(TextValue):
    value: str = """
کاربر عزیز لطفا برای اینکه شماره کارت به شما نمایش داده‌شود حساب خود را از طریق پشتیبانی تأیید کنید!

"""


class Texts(BaseTexts):
    choose_amount: ChooseAmountText = ChooseAmountText()
    show_invoice: ShowInvoiceText = ShowInvoiceText()
    not_verified_for_show: NotVerifiedForShow = NotVerifiedForShow()


from datetime import datetime as dt
from typing import Literal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app import main
from app.handlers import base as base_handlers
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.user import payment
from app.models.setting import Card
from app.models.user import CardToCardPayment, Invoice, Transaction, User
from app.plugins.payment.jobs import activate_service, revoke_activated_transaction
from app.utils import settings, texts
from app.utils.filters import AdminAccess, IsSuperUser
from app.utils.values import admin_edit_texts_format, check_texts

router = Router(name="payment/card_to_card")

_admin_receipt_messages: dict[int, set[tuple[int, int]]] = {}


# # Admin settings Start
cancel_admin_form = CancelFormAdmin().as_markup(
    resize_keyboard=True, one_time_only=True
)


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="set_card_to_card"):
        field: Fields
        confirmed: bool = False

    def __init__(self, settings: Settings, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'فعال ✅' if settings.enabled else 'غیرفعال ❌'}",
            callback_data=self.Callback(field=Fields.enabled),
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
            text="ویرایش متن 'تأیید قبل از نمایش شماره کارت'",
            callback_data=self.Callback(field=Fields.text_not_verified_for_show),
        )
        self.button(
            text=f"تأیید کاربر قبل از نمایش کارت: {'✅' if settings.verify_before_show_card else '❌'}",
            callback_data=self.Callback(
                field=Fields.verify_before_show_card,
            ),
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
            text="مدیریت کارت‌ها",
            callback_data=self.Callback(field=Fields.cards),
        )
        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1, 1)


class TextsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="txt_card_to_card"):
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


class CardToCardEditForm(StatesGroup):
    menu_title = State()
    min_pay_amount = State()

    free_after = State()
    free_after_percent = State()

    text_choose_amount = State()
    text_show_invoice = State()
    text_not_verified_for_show = State()


class CardToCardCustomAmountForm(StatesGroup):
    method = State()
    amount = State()


@router.message(
    StateFilter(CardToCardEditForm),
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
    _settings = settings.get_settings().payment_card_to_card
    text = f"""
نام مستعار: <b>{_settings.menu_title}</b>

حداقل مبلغ قابل پرداخت: <code>{_settings.min_pay_amount}</code>

اعتبار هدیه برای مبلغ بیشتر از: <code>{_settings.free_after:,}</code>
درصد اعتبار هدیه: <code>{_settings.free_after_percent} %</code>

نیاز به تأیید کاربر قبل از نمایش شماره کارت: {'✅' if _settings.verify_before_show_card else '❌'}

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
async def edit_settings_is_enabled(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_card_to_card
    if _settings.enabled:
        _settings.enabled = False
        text = "درگاه کارت به کارت غیرفعال شد!"
    else:
        _settings.enabled = True
        text = "درگاه کارت به کارت فعال شد!"
    await settings.Settings.update(payment_card_to_card=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.verify_before_show_card),
    IsSuperUser(),
)
async def edit_settings_verify_before_show_card(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_card_to_card
    if _settings.verify_before_show_card:
        _settings.verify_before_show_card = False
        text = "نیاز به تأیید کاربر برای نمایش شماره کارت غیرفعال شد!"
    else:
        _settings.verify_before_show_card = True
        text = """
نیاز به تأیید کاربر قبل از نمایش شماره کارت فعال شد!

از منوی تنظیمات کاربر می‌توانید کاربر را تأیید کنید.
"""
    await settings.Settings.update(payment_card_to_card=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.field.in_(
            [
                Fields.text_choose_amount,
                Fields.text_show_invoice,
                Fields.text_not_verified_for_show,
            ]
        )
    ),
    IsSuperUser(),
)
async def edit_settings_texts(
    qmsg: CallbackQuery | Message, user: User, callback_data: SettingsKeyboard.Callback
):
    _texts = texts.get_texts()
    ed_text = None
    if callback_data.field == Fields.text_choose_amount:
        ed_text = _texts.payment_card_to_card.choose_amount
    elif callback_data.field == Fields.text_show_invoice:
        ed_text = _texts.payment_card_to_card.show_invoice
    elif callback_data.field == Fields.text_not_verified_for_show:
        ed_text = _texts.payment_card_to_card.not_verified_for_show
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
    _texts = texts.get_texts().payment_card_to_card
    if callback_data.field == Fields.text_choose_amount:
        _texts.choose_amount = ChooseAmountText()
    elif callback_data.field == Fields.text_show_invoice:
        _texts.show_invoice = ShowInvoiceText()
    elif callback_data.field == Fields.text_not_verified_for_show:
        _texts.not_verified_for_show = NotVerifiedForShow()
    else:
        return await query.answer(
            f"بازنشانی متن برای {callback_data.field.name} تعریف نشده است!"
        )
    await texts.Texts.update(payment_card_to_card=_texts)
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
        await state.set_state(CardToCardEditForm.text_choose_amount)
    elif callback_data.field == Fields.text_show_invoice:
        await state.set_state(CardToCardEditForm.text_show_invoice)
    elif callback_data.field == Fields.text_not_verified_for_show:
        await state.set_state(CardToCardEditForm.text_not_verified_for_show)
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
    CardToCardEditForm.text_choose_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts().payment_card_to_card

    if not await check_texts(_texts.choose_amount, message):
        return
    _texts.choose_amount = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_card_to_card=_texts)
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
    CardToCardEditForm.text_show_invoice,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts().payment_card_to_card

    if not await check_texts(_texts.show_invoice, message):
        return
    _texts.show_invoice = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_card_to_card=_texts)
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


@router.message(
    CardToCardEditForm.text_not_verified_for_show,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts().payment_card_to_card

    if not await check_texts(_texts.not_verified_for_show, message):
        return
    _texts.not_verified_for_show = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_card_to_card=_texts)
    await texts.reload_texts()
    text = f"""
متن not_verified_for_show با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsKeyboard.Callback(
            field=Fields.text_not_verified_for_show
        ),
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(~F.field.in_([Fields.cards])),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings().payment_card_to_card
    if callback_data.field == Fields.min_pay_amount:
        text = "مقدار جدید حداقل مبلغ قابل پرداخت را به تومان وارد کنید:"
        await state.set_state(CardToCardEditForm.min_pay_amount)

    elif callback_data.field == Fields.menu_title:
        text = "مقدار جدید نام مستعار را وارد کنید:"
        await state.set_state(CardToCardEditForm.menu_title)

    elif callback_data.field == Fields.free_after:
        text = f"تراکنش‌ها از چه مبلغی به بعد شامل {_settings.free_after_percent} درصد اعتبار هدیه شوند؟ برای غیرفعال سازی 0 را وارد کنید:"
        await state.set_state(CardToCardEditForm.free_after)

    elif callback_data.field == Fields.free_after_percent:
        if not _settings.free_after:
            return await query.answer(
                "ابتدا اعتبار هدیه را فعال کرده و سپس درصد را تنظیم کنید!"
            )
        text = f"تراکنش‌های بیشتر از {_settings.free_after:,} شامل چند درصد اعتبار هدیه شوند؟"
        await state.set_state(CardToCardEditForm.free_after_percent)
    else:
        return await query.answer(
            f"تنظیمات برای {callback_data.field.value} تعریف نشده است!", show_alert=True
        )
    await query.message.reply(
        text=text,
        reply_markup=cancel_admin_form,
    )


@router.message(
    CardToCardEditForm.menu_title,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_menu_title(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_card_to_card
    menu_title = message.text.strip().replace("\n", " ")
    origv = _settings.menu_title
    _settings.menu_title = menu_title
    await settings.Settings.update(payment_card_to_card=_settings)
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
    CardToCardEditForm.min_pay_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_min_pay_amount(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_card_to_card
    try:
        min_pay_amount = int(message.text)
    except ValueError:
        return await message.reply(
            f"{message.text} مقداری نامعتبر است! لطفا مقداری عددی وارد کنید:"
        )
    origv = _settings.min_pay_amount
    _settings.min_pay_amount = min_pay_amount
    await settings.Settings.update(payment_card_to_card=_settings)
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
    CardToCardEditForm.free_after,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_card_to_card
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
    await settings.Settings.update(payment_card_to_card=_settings)
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
    CardToCardEditForm.free_after_percent,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after_percent(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_card_to_card
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
    await settings.Settings.update(payment_card_to_card=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{free_after_percent}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


class CardsActions(str, Enum):
    show = "show"
    remove = "remove"
    add_new = "add_new"
    save_new = "save_new"
    edit_card_number = "edit_number"
    edit_card_holder = "edit_holder"
    flip_status = "flip_status"


class CardsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="cards"):
        card_id: int = 0
        action: CardsActions

    def __init__(self, cards: list[Card], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for card in cards:
            self.button(
                text=f"{'✅' if card.is_active else '❌'} {card.card_number} | {card.card_holder}",
                callback_data=self.Callback(card_id=card.id, action=CardsActions.show),
            )
        self.button(
            text="افزودن کارت",
            callback_data=self.Callback(action=CardsActions.add_new),
        )
        self.button(text="برگشت", callback_data=f"pm:settings:{SETTINGS_KEY_PREFIX}")
        self.adjust(1, 1)


class SaveNewCard(InlineKeyboardBuilder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="ذخیره این کارت",
            callback_data=CardsKeyboard.Callback(action=CardsActions.save_new),
        )
        self.button(
            text="لغو",
            callback_data=SettingsKeyboard.Callback(field=Fields.cards),
        )
        self.adjust(1, 1)


class CardKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="crdsact"):
        card_id: int
        action: CardsActions
        confirmed: bool = False

    def __init__(self, card: Card, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'✅' if card.is_active else '❌'}",
            callback_data=self.Callback(
                card_id=card.id, action=CardsActions.flip_status
            ),
        )
        self.button(
            text="ویرایش نام صاحب کارت",
            callback_data=self.Callback(
                card_id=card.id, action=CardsActions.edit_card_holder
            ),
        )
        self.button(
            text="ویرایش شماره کارت",
            callback_data=self.Callback(
                card_id=card.id, action=CardsActions.edit_card_number
            ),
        )
        self.button(
            text="حذف کارت",
            callback_data=self.Callback(card_id=card.id, action=CardsActions.remove),
        )
        self.button(
            text="برگشت",
            callback_data=SettingsKeyboard.Callback(field=Fields.cards),
        )
        self.adjust(1, 1, 1)


class ConfirmCardKeyboard(InlineKeyboardBuilder):
    def __init__(self, card: Card, action: CardsActions, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.button(
            text="تایید",
            callback_data=CardKeyboard.Callback(
                card_id=card.id, action=action, confirmed=True
            ),
        )
        self.button(
            text="برگشت",
            callback_data=CardKeyboard.Callback(
                card_id=card.id, action=CardsActions.show
            ),
        )


class AddCardForm(StatesGroup):
    card_number = State()
    card_holder = State()


class EditCardForm(StatesGroup):
    card_id = State()
    card_number = State()
    card_holder = State()


@router.message(
    StateFilter(AddCardForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
    ~CommandStart(),
    ~Command("menu"),
)
@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field.in_([Fields.cards])),
    IsSuperUser(),
)
async def show_cards(
    query: CallbackQuery | Message, user: User, state: FSMContext | None = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="عملیات لغو شد!", reply_markup=ReplyKeyboardRemove())
    db_cards = await Card.all()
    cards = CardsKeyboard(cards=db_cards).as_markup()
    text = f"لیست کارت‌های اضافه شده: ({len(db_cards)})"
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text(text=text, reply_markup=cards)
    return await query.answer(text=text, reply_markup=cards)


# Add Cards
@router.callback_query(
    CardsKeyboard.Callback.filter(F.action == CardsActions.add_new),
    IsSuperUser(),
)
async def add_card(query: CallbackQuery, user: User, state: FSMContext):
    await state.set_state(AddCardForm.card_number)
    await query.message.answer(
        "شماره کارت ۱۶ رقمی را وارد کنید:",
        reply_markup=cancel_admin_form,
    )


@router.message(
    AddCardForm.card_number,
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_card_number(message: Message, user: User, state: FSMContext):
    if (len(message.text) != 16) or not message.text.isnumeric():
        return await message.answer("شماره کارت باید ۱۶ رقمی و مقداری عددی باشد!")
    if await Card.filter(card_number=message.text).first():
        return message.answer(
            "این شماره کارت از قبل وارد شده است! دوباره تلاش کنید::",
            reply_markup=cancel_admin_form,
        )
    await state.update_data(card_number=message.text)
    await state.set_state(AddCardForm.card_holder)
    await message.answer(
        "نام صاحب کارت را وارد کنید:",
        reply_markup=cancel_admin_form,
    )


@router.message(
    AddCardForm.card_holder,
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_card_holder(message: Message, user: User, state: FSMContext):
    await state.update_data(card_holder=message.text)
    data = await state.get_data()
    text = f"""
شماره کارت: <code>{data.get('card_number')}</code>
صاحب کارت: <code>{data.get('card_holder')}</code>
"""
    await message.answer(
        text,
        reply_markup=SaveNewCard().as_markup(),
    )


@router.callback_query(
    CardsKeyboard.Callback.filter(F.action == CardsActions.save_new),
    IsSuperUser(),
    StateFilter(AddCardForm),
)
async def save_new_card(query: CallbackQuery, user: User, state: FSMContext):
    data = await state.get_data()
    card = await Card.create(
        card_number=data.get("card_number"), card_holder=data.get("card_holder")
    )
    await query.answer("کارت جدید با موفقیت ذخیره!")
    await state.clear()
    await show_card(
        query,
        user,
        callback_data=CardKeyboard.Callback(card_id=card.id, action=CardsActions.show),
    )


@router.message(
    StateFilter(EditCardForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
    ~CommandStart(),
    ~Command("menu"),
)
@router.callback_query(
    CardsKeyboard.Callback.filter(F.action == CardsActions.show),
    IsSuperUser(),
)
async def show_card(
    qmsg: CallbackQuery | Message, user: User, callback_data=CardsKeyboard.Callback
):
    card = await Card.filter(id=callback_data.card_id).first()
    if not card:
        await qmsg.answer("کارت یافت نشد!")
        return await show_cards(qmsg, user)
    text = f"""
شناسه کارت: <code>{card.id}</code>
شماره کارت: <code>{card.card_number}</code>
صاحب کارت: <code>{card.card_holder}</code>
"""
    markup = CardKeyboard(card).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


# Remove Cards
@router.callback_query(
    CardKeyboard.Callback.filter(F.action == CardsActions.remove),
    IsSuperUser(),
)
async def remove_card(
    query: CallbackQuery, user: User, callback_data: CardKeyboard.Callback
):
    card = await Card.filter(id=callback_data.card_id).first()
    if not card:
        await query.answer("کارت یافت نشد!", show_alert=True)
        return await show_cards(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        text = """
کارت حذف شود؟: 

❗️❗️<strong>این عمل غیرقابل بازگشت می‌باشد! می‌توانید به جای این کارت وضعیت کارت را غیرفعال کنید.</strong>
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmCardKeyboard(
                card=card, action=CardsActions.remove
            ).as_markup(),
        )
    await card.delete()
    await query.answer("کارت حذف شد!", show_alert=True)
    return await show_cards(query, user)


# Update Cards
@router.callback_query(
    CardKeyboard.Callback.filter(F.action == CardsActions.flip_status),
    IsSuperUser(),
)
async def edit_cards(
    query: CallbackQuery, user: User, callback_data: CardKeyboard.Callback
):
    card = await Card.filter(id=callback_data.card_id).first()
    if not card:
        await query.answer("کارت یافت نشد!", show_alert=True)
        return await show_cards(
            query,
            user,
        )
    if card.is_active:
        card.is_active = False
        text = "کارت غیرفعال شد!"
    else:
        card.is_active = True
        text = "کارت فعال شد!"
    await card.save()
    await query.answer(text, show_alert=True)
    await show_card(
        query,
        user,
        callback_data=CardKeyboard.Callback(card_id=card.id, action=CardsActions.show),
    )


@router.callback_query(
    CardKeyboard.Callback.filter(F.action == CardsActions.edit_card_number),
    IsSuperUser(),
)
async def edit_cards(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: CardKeyboard.Callback,
    state: FSMContext,
):
    await state.set_state(EditCardForm.card_number)
    await state.update_data(card_id=callback_data.card_id)
    await query.message.answer(
        "شماره کارت ۱۶ رقمی جدید را وارد کنید:",
        reply_markup=cancel_admin_form,
    )


@router.callback_query(
    CardKeyboard.Callback.filter(F.action == CardsActions.edit_card_holder),
    IsSuperUser(),
)
async def edit_cards(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: CardKeyboard.Callback,
    state: FSMContext,
):
    await state.set_state(EditCardForm.card_holder)
    await state.update_data(card_id=callback_data.card_id)
    await query.message.answer(
        "نام جدید صاحب کارت را وارد کنید:",
        reply_markup=cancel_admin_form,
    )


@router.message(
    EditCardForm.card_number,
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_card_number(message: Message, user: User, state: FSMContext):  # noqa: F811
    if (len(message.text) != 16) or not message.text.isnumeric():
        return await message.answer("شماره کارت باید ۱۶ رقمی و مقداری عددی باشد!")
    if await Card.filter(card_number=message.text).first():
        return message.answer(
            "این شماره کارت از قبل وارد شده است! دوباره تلاش کنید:",
            reply_markup=cancel_admin_form,
        )
    card_id = (await state.get_data()).get("card_id")
    card = await Card.filter(id=card_id).first()
    if not card:
        await state.clear()
        return await message.answer("خطایی در انجام عملیات رخ داد!")
    card.card_number = message.text
    await card.save(update_fields=["card_number"])
    await show_card(
        message,
        user,
        callback_data=CardsKeyboard.Callback(card_id=card.id, action=CardsActions.show),
    )


@router.message(
    EditCardForm.card_holder,
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_card_number(message: Message, user: User, state: FSMContext):  # noqa: F811
    card_id = (await state.get_data()).get("card_id")
    card = await Card.filter(id=card_id).first()
    if not card:
        await state.clear()
        return await message.answer("خطایی در انجام عملیات رخ داد!")
    card_holder = message.text.replace("\n", " ")
    if card_holder == card.card_holder:
        return message.answer(
            "نام وارد شده نمی‌تواند برابر بانام قدیمی باشد! دوباره تلاش کنید:",
            reply_markup=cancel_admin_form,
        )
    card.card_holder = message.text
    await card.save(update_fields=["card_holder"])
    await show_card(
        message,
        user,
        callback_data=CardsKeyboard.Callback(card_id=card.id, action=CardsActions.show),
    )


# # Admin Settings End

# # User handlers Start


class NoCardAvailable(Exception):
    pass


@router.message(
    F.text.in_([base.MainMenu.cancel, base.MainMenu.back]),
    ~CommandStart(),
    ~Command("menu"),
    StateFilter(CardToCardCustomAmountForm),
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
    if not _settings.payment_card_to_card.enabled or (
        await Card.filter(is_active=True).count() < 1
    ):
        if isinstance(qmsg, CallbackQuery):
            text = f"📍 در حال حاضر امکان پرداخت از طریق {_settings.payment_card_to_card.menu_title} وجود ندارد!"
            return await qmsg.answer(text=text, show_alert=True)
        return await qmsg.answer(text=text)
    _texts = texts.get_texts().payment_card_to_card
    if (
        (user.role < User.Role.admin)
        and _settings.payment_card_to_card.verify_before_show_card
        and not user.is_verified
    ):
        text = texts.Texts.format(_texts.not_verified_for_show)
        markup = payment.SelectPayAmount(
            method=SETTINGS_KEY_PREFIX,
            _settings=_settings,
            is_verified=False,
        ).as_markup()
    else:
        text = texts.Texts.format(
            _texts.choose_amount,
            PAYMENT_PROVIDER_TITLE=_settings.payment_card_to_card.menu_title,
            MINIMUM_PAY_AMOUNT=_settings.payment_card_to_card.min_pay_amount,
        )
        markup = payment.SelectPayAmount(
            method=SETTINGS_KEY_PREFIX,
            _settings=_settings,
        ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


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
    await state.set_state(CardToCardCustomAmountForm.amount)
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
    CardToCardCustomAmountForm.amount,
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
        state=state,
    )


class CardToCardReceiptForm(StatesGroup):
    id = State()
    photo = State()


class CardToCardAdminAccept(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="crdtcrdverf"):
        transaction_id: int
        action: Literal["accept", "reject", "reject_cancel"]
        confirmed: bool = False

    def __init__(self, transaction: Transaction, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.has_buttons = False
        if transaction.status == Transaction.Status.waiting:
            self.button(
                text="✅ تأیید فیش",
                callback_data=self.Callback(
                    transaction_id=transaction.id, action="accept"
                ),
            )
            self.has_buttons = True
            self.button(
                text="❌ رد فیش",
                callback_data=self.Callback(
                    transaction_id=transaction.id, action="reject"
                ),
            )
            self.has_buttons = True
        elif transaction.status == Transaction.Status.finished:
            self.button(
                text="❌ لغو تأیید و حذف سرویس",
                callback_data=self.Callback(
                    transaction_id=transaction.id, action="reject"
                ),
            )
            self.has_buttons = True
        self.adjust(1, 1)


class CardToCardRejectConfirm(InlineKeyboardBuilder):
    """Confirm step shown before rejecting an *already-accepted* receipt, since
    that now also removes the customer's subscription."""

    def __init__(self, transaction_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="✅ بله، حذف و رد کن",
            callback_data=CardToCardAdminAccept.Callback(
                transaction_id=transaction_id, action="reject", confirmed=True
            ),
        )
        self.button(
            text="↩️ انصراف",
            callback_data=CardToCardAdminAccept.Callback(
                transaction_id=transaction_id, action="reject_cancel"
            ),
        )
        self.adjust(1, 1)


def _html(value: object | None, default: str = "ثبت نشده") -> str:
    text = str(value).strip() if value is not None else ""
    return escape(text or default, quote=False)


def _status_label(status: Transaction.Status) -> str:
    labels = {
        Transaction.Status.waiting: "⏳ در انتظار بررسی",
        Transaction.Status.finished: "✅ تأیید شده",
        Transaction.Status.rejected: "❌ رد شده",
        Transaction.Status.failed: "⚠️ ناموفق",
        Transaction.Status.canceled: "🚫 لغو شده",
        Transaction.Status.confirming: "🔎 در حال بررسی",
        Transaction.Status.sending: "📨 در حال ارسال",
        Transaction.Status.partially_paid: "⚠️ پرداخت ناقص",
    }
    return labels.get(status, "نامشخص")


def _invoice_type_label(invoice: Invoice | None) -> str:
    if not invoice:
        return "شارژ کیف پول"
    labels = {
        Invoice.Type.purchase: "خرید سرویس جدید",
        Invoice.Type.renew_now: "تمدید فوری سرویس",
        Invoice.Type.renew_reserve: "رزرو تمدید سرویس",
        Invoice.Type.parent_charged_child: "شارژ زیرمجموعه",
        Invoice.Type.by_admin: "ثبت توسط ادمین",
    }
    return labels.get(invoice.type, "درخواست پرداخت")


async def _load_card_to_card_transaction(transaction_id: int) -> Transaction | None:
    return (
        await Transaction.filter(
            id=transaction_id,
            type=Transaction.PaymentType.card_to_card,
        )
        .first()
        .prefetch_related(
            "user",
            "card_to_card_payment",
            "card_to_card_payment__destination_card",
        )
    )


async def _load_transaction_invoice(transaction_id: int) -> Invoice | None:
    return (
        await Invoice.filter(transaction_id=transaction_id)
        .first()
        .prefetch_related("service", "proxy")
    )


def _admin_receipt_markup(transaction: Transaction):
    builder = CardToCardAdminAccept(transaction=transaction)
    return builder.as_markup() if builder.has_buttons else None


def _message_target(message: Message) -> tuple[int, int]:
    return message.chat.id, message.message_id


async def _remember_admin_receipt_message(
    transaction_id: int, message: Message
) -> None:
    target = _message_target(message)
    _admin_receipt_messages.setdefault(transaction_id, set()).add(target)

    payment = await CardToCardPayment.filter(transaction_id=transaction_id).first()
    if not payment:
        return
    saved = payment.admin_messages if isinstance(payment.admin_messages, list) else []
    saved_targets: set[tuple[int, int]] = set()
    for item in saved:
        if not isinstance(item, dict):
            continue
        try:
            saved_targets.add((int(item["chat_id"]), int(item["message_id"])))
        except (KeyError, TypeError, ValueError):
            continue
    if target in saved_targets:
        return
    payment.admin_messages = [
        *saved,
        {"chat_id": target[0], "message_id": target[1]},
    ]
    await payment.save(update_fields=["admin_messages"])


async def _admin_receipt_targets(transaction_id: int) -> set[tuple[int, int]]:
    targets = set(_admin_receipt_messages.get(transaction_id, set()))
    payment = await CardToCardPayment.filter(transaction_id=transaction_id).first()
    saved = (
        payment.admin_messages
        if payment and isinstance(payment.admin_messages, list)
        else []
    )
    for item in saved:
        if not isinstance(item, dict):
            continue
        try:
            targets.add((int(item["chat_id"]), int(item["message_id"])))
        except (KeyError, TypeError, ValueError):
            continue
    return targets


async def _admin_receipt_text(transaction: Transaction) -> str:
    transaction = await _load_card_to_card_transaction(transaction.id) or transaction
    invoice = await _load_transaction_invoice(transaction.id)
    user = transaction.user
    card_payment = transaction.card_to_card_payment
    card = card_payment.destination_card if card_payment else None
    paid_amount = transaction.amount - transaction.amount_free_given

    username = f"@{_html(user.username)}" if user.username else "ثبت نشده"
    user_name = _html(user.custom_name or user.name)
    phone = _html(user.phone_number)
    card_number = (
        _html(format_card_number(card.card_number)) if card else "ثبت نشده"
    )
    card_holder = _html(card.card_holder) if card else "ثبت نشده"

    order_lines = [
        f"• نوع درخواست: <b>{_invoice_type_label(invoice)}</b>",
    ]
    if invoice:
        order_lines.append(f"• شماره فاکتور داخلی: <code>{invoice.id}</code>")
        if invoice.service:
            order_lines.append(
                f"• پلن/تعرفه: <b>{_html(invoice.service.display_name)}</b>"
            )
        if invoice.proxy:
            order_lines.append(
                f"• اشتراک مرتبط: <code>{_html(invoice.proxy.username)}</code>"
            )
    else:
        order_lines.append("• پلن/تعرفه: <b>شارژ حساب بدون خرید مستقیم</b>")

    gift_line = ""
    if transaction.amount_free_given:
        gift_line = (
            f"\n• هدیه/بونوس: <b>{transaction.amount_free_given:,}</b> تومان"
            f"\n• اعتبار نهایی: <b>{transaction.amount:,}</b> تومان"
        )

    return f"""
🧾 <b>فیش جدید کارت به کارت</b>

📌 <b>وضعیت</b>
• {_status_label(transaction.status)}
• شماره تراکنش: <code>{transaction.id}</code>

👤 <b>کاربر</b>
• شناسه: <a href="tg://user?id={user.id}">{user.id}</a>
• نام: <b>{user_name}</b>
• یوزرنیم: <code>{username}</code>
• شماره تماس: <code>{phone}</code>

💳 <b>پرداخت</b>
• مبلغ پرداختی: <b>{paid_amount:,}</b> تومان{gift_line}
• کارت مقصد: <code>{card_number}</code>
• صاحب کارت: <b>{card_holder}</b>

🛒 <b>جزئیات سفارش</b>
{chr(10).join(order_lines)}

🔎 <b>بررسی کاربر</b>
https://t.me/{main.get_bot_username()}?start=info_{user.id}
""".strip()


async def _edit_admin_receipt_message(
    message: Message,
    transaction: Transaction,
    reply_markup=None,
) -> None:
    await _remember_admin_receipt_message(transaction.id, message)
    text = await _admin_receipt_text(transaction)
    if reply_markup is None:
        reply_markup = _admin_receipt_markup(transaction)
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


async def _sync_admin_receipt_messages(
    bot,
    transaction: Transaction,
    current_message: Message | None = None,
) -> None:
    transaction = await _load_card_to_card_transaction(transaction.id) or transaction
    if current_message:
        await _remember_admin_receipt_message(transaction.id, current_message)

    text = await _admin_receipt_text(transaction)
    reply_markup = _admin_receipt_markup(transaction)
    targets = await _admin_receipt_targets(transaction.id)
    for chat_id, message_id in targets:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def _finish_waiting_transaction(transaction: Transaction) -> bool:
    updated = await Transaction.filter(
        id=transaction.id,
        type=Transaction.PaymentType.card_to_card,
        status=Transaction.Status.waiting,
    ).update(
        status=Transaction.Status.finished,
        finished_at=dt.now(),
        amount_paid=transaction.amount - transaction.amount_free_given,
    )
    return bool(updated)


async def _reject_waiting_transaction(transaction: Transaction) -> bool:
    updated = await Transaction.filter(
        id=transaction.id,
        type=Transaction.PaymentType.card_to_card,
        status=Transaction.Status.waiting,
    ).update(status=Transaction.Status.rejected)
    return bool(updated)


@router.callback_query(
    payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX),
)
async def select_amount(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings().payment_card_to_card
    if not _settings.enabled or (await Card.filter(is_active=True).count() < 1):
        if isinstance(qmsg, CallbackQuery):
            text = f"📍 در حال حاضر امکان پرداخت از طریق {_settings.menu_title} وجود ندارد!"
            return await qmsg.answer(text=text, show_alert=True)
        return await qmsg.answer(text=text)
    _texts = texts.get_texts().payment_card_to_card
    if (
        (user.role < User.Role.admin)
        and _settings.verify_before_show_card
        and not user.is_verified
    ):
        text = texts.Texts.format(_texts.not_verified_for_show)
        markup = payment.SelectPayAmount(
            method=SETTINGS_KEY_PREFIX,
            _settings=_settings,
            is_verified=False,
            back_callback=payment.ChargePanel.DirectCallback(
                amount=callback_data.amount,
                service_id=callback_data.service_id,
                menu_id=callback_data.menu_id,
                proxy_id=callback_data.proxy_id,
                mode=callback_data.direct_mode,
            ),
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=markup)
        return await qmsg.answer(text, reply_markup=markup)
    await qmsg.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        async with in_transaction():
            transaction = await Transaction.create(
                type=Transaction.PaymentType.card_to_card,
                status=Transaction.Status.waiting,
                amount=callback_data.amount + callback_data.free,
                amount_free_given=callback_data.free,
                user=user,
            )
            if callback_data.direct_mode is not None:
                if callback_data.direct_mode == "renew":
                    invoice_type = Invoice.Type.renew_now
                elif callback_data.direct_mode == "reserve":
                    invoice_type = Invoice.Type.renew_reserve
                else:
                    invoice_type = Invoice.Type.purchase
                await Invoice.create(
                    amount=callback_data.amount,
                    type=invoice_type,
                    is_paid=False,
                    is_draft=True,
                    service_id=callback_data.service_id or None,
                    proxy_id=callback_data.proxy_id or None,
                    user=user,
                    transaction=transaction,
                )
            card = await Card.get_random()
            if not card:
                raise NoCardAvailable("no card available for card to card payment!")

            await CardToCardPayment.create(
                transaction=transaction,
                destination_card=card,
            )
        text = texts.Texts.format(
            _texts.show_invoice,
            PAYMENT_PROVIDER_TITLE=_settings.menu_title,
            TRANSACTION_ID=transaction.id,
            AMOUNT_TOMAN=transaction.amount - transaction.amount_free_given,
            CARD_HOLDER=card.card_holder,
            CARD_NUMBER=card.card_number,
        )
        await state.set_state(CardToCardReceiptForm.photo)
        await state.set_data({"id": transaction.id})
        markup = base.CancelUserForm(cancel=True).as_markup(
            resize_keyboard=True, one_time_keyboard=True
        )
        if isinstance(qmsg, CallbackQuery):
            await qmsg.message.edit_text(
                text=text,
            )
            await qmsg.message.reply(
                "💠 رسید پرداخت را ارسال کنید:", reply_markup=markup
            )
            return
        msg = await qmsg.answer(text=text)
        await msg.reply("💠 رسید پرداخت را ارسال کنید:", reply_markup=markup)
    except NoCardAvailable as err:
        await qmsg.answer(
            f"📍 در حال حاضر امکان پرداخت از طریق {_settings.menu_title} وجود ندارد!"
        )
        raise err


@router.message(
    CardToCardReceiptForm.photo,
    ~(F.text.casefold() == base.MainMenu.cancel),
    ~(F.text.casefold() == base.MainMenu.main_menu),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_card_to_card_reciepts(message: Message, user: User, state: FSMContext):
    if not message.photo:
        return await message.reply(
            "⚠️ لطفا رسید خود را به صورت عکس ارسال کنید:",
            reply_markup=base.CancelUserForm(cancel=True).as_markup(
                resize_keyboard=True, one_time_keyboard=True
            ),
        )
    _settings = settings.get_settings()
    trx_id = (await state.get_data()).get("id")
    if trx_id is None:
        return await message.reply("❌ خطایی رخ داد! لطفا با پشتیبانی تماس بگیرید!")
    transaction = (
        await Transaction.filter(
            id=int(trx_id), type=Transaction.PaymentType.card_to_card
        )
        .first()
        .prefetch_related(
            "card_to_card_payment", "card_to_card_payment__destination_card"
        )
    )
    if not transaction:
        return await message.reply("❌ خطایی رخ داد! لطفا با پشتیبانی تماس بگیرید!")
    text = await _admin_receipt_text(transaction)

    async def send_reciept(chats: list[str | int]) -> list[Message]:
        reciept_messages = []
        for chat in chats:
            try:
                msg = await message.forward(chat)
                reciept_msg = await msg.reply(
                    text=text,
                    reply_markup=_admin_receipt_markup(transaction),
                )
                await _remember_admin_receipt_message(transaction.id, reciept_msg)
                reciept_messages.append(reciept_msg)
            except (TelegramBadRequest, TelegramForbiddenError):
                if chat == _settings.transaction_logs:
                    return await send_reciept(config.SUPER_USERS)
        return reciept_messages

    if reciept_messages := await send_reciept(
        [_settings.transaction_logs]
        if _settings.transaction_logs
        else config.SUPER_USERS
    ):
        await message.reply(
            "✅ رسید پرداخت شما ثبت شد! بعد از تأیید مبلغ پرداختی به حساب شما اضافه خواهد شد."
        )
        # accept automatically
        if user.card_to_card_auto_accept:
            accepted = await _finish_waiting_transaction(transaction)
            transaction = await _load_card_to_card_transaction(transaction.id)
            if transaction:
                await _sync_admin_receipt_messages(message.bot, transaction)
            if not accepted or not transaction:
                await state.clear()
                return await base_handlers.main_menu_handler(message, user)
            text = f"""
✅ پرداخت شما از طریق کارت به کارت با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount - transaction.amount_free_given:,}</b> تومان
‌‌
"""
            msg = await message.answer(text=text)
            # Auto-accept must also activate a direct purchase/renew, exactly
            # like the manual-accept path — otherwise the wallet is credited but
            # the subscription is never created/renewed.
            activate_service(transaction, msg)
    else:
        await message.reply(
            "❌ خطایی در ثبت رسید پرداخت رخ داد! لطفا با پشتیبانی تماس بگیرید!"
        )
    await state.clear()
    await base_handlers.main_menu_handler(message, user)


@router.callback_query(
    CardToCardAdminAccept.Callback.filter(F.action == "reject_cancel"), AdminAccess()
)
async def admin_reject_cancel_card_to_card_receipt(
    query: CallbackQuery, user: User, callback_data: CardToCardAdminAccept.Callback
):
    """Cancel the reject confirmation: restore the original accept/reject menu."""
    transaction = await _load_card_to_card_transaction(callback_data.transaction_id)
    if not transaction:
        return await query.answer("تراکنش یافت نشد!", show_alert=True)
    await _edit_admin_receipt_message(query.message, transaction)
    return await query.answer("لغو شد")


@router.callback_query(
    CardToCardAdminAccept.Callback.filter(F.action == "reject"), AdminAccess()
)
async def admin_reject_card_to_card_receipt(
    query: CallbackQuery, user: User, callback_data: CardToCardAdminAccept.Callback
):
    transaction = await _load_card_to_card_transaction(callback_data.transaction_id)
    if not transaction:
        return await query.answer("Transaction not found!", show_alert=True)
    if transaction.status == Transaction.Status.rejected:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        return await query.answer("این تراکنش قبلاً رد شده است!", show_alert=True)

    # Already accepted → rejecting now also removes the subscription, so confirm
    # first (per owner's choice). A not-yet-accepted (waiting) receipt has
    # nothing to undo, so it rejects in one tap as before.
    was_activated = transaction.status == Transaction.Status.finished
    if was_activated and not callback_data.confirmed:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        await query.answer(
            "⚠️ این تراکنش قبلاً تأیید شده و اشتراک ساخته شده! با رد کردن، اشتراک کاربر حذف و فاکتور باطل می‌شود.",
            show_alert=True,
        )
        await _edit_admin_receipt_message(
            query.message,
            transaction,
            reply_markup=CardToCardRejectConfirm(
                transaction_id=transaction.id
            ).as_markup(),
        )
        return

    if not was_activated and transaction.status != Transaction.Status.waiting:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        return await query.answer(
            "وضعیت فعلی این تراکنش اجازه رد کردن ندارد.", show_alert=True
        )

    if was_activated:
        summary = await revoke_activated_transaction(transaction)
        transaction = await _load_card_to_card_transaction(transaction.id)
    else:
        updated = await _reject_waiting_transaction(transaction)
        transaction = await _load_card_to_card_transaction(transaction.id)
        summary = ""
        if not updated:
            if transaction:
                await _sync_admin_receipt_messages(query.bot, transaction, query.message)
            return await query.answer(
                "وضعیت این فیش توسط ادمین دیگری تغییر کرده است.", show_alert=True
            )
    if not transaction:
        return await query.answer("تراکنش یافت نشد!", show_alert=True)
    await _sync_admin_receipt_messages(query.bot, transaction, query.message)
    await query.answer("تراکنش رد شد!", show_alert=True)

    amount = transaction.amount - transaction.amount_free_given
    if was_activated:
        user_text = f"""
❌ پرداخت کارت به کارت شما به شماره فاکتور {transaction.id} و مبلغ {amount:,} تومان توسط پشتیبانی تأیید نشد و اشتراک مربوطه لغو شد!
برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.
"""
    else:
        user_text = f"""
تراکنش کارت به کارت شما به شماره فاکتور {transaction.id} و مبلغ {amount:,} تومان توسط پشتیبانی تأیید نشد!
برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.
"""
    try:
        await query.bot.send_message(transaction.user_id, text=user_text)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    if was_activated and summary:
        try:
            await query.message.reply(f"🧾 نتیجه لغو فعال‌سازی:\n{summary}")
        except TelegramBadRequest:
            pass


@router.callback_query(
    CardToCardAdminAccept.Callback.filter(F.action == "accept"), AdminAccess()
)
async def admin_accept_card_to_card_receipt(
    query: CallbackQuery,
    user: User,
    callback_data: CardToCardAdminAccept.Callback,
):
    transaction = await _load_card_to_card_transaction(callback_data.transaction_id)
    if not transaction:
        return await query.answer("تراکنش یافت نشد!", show_alert=True)

    if transaction.status == Transaction.Status.finished:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        return await query.answer("تراکنش از قبل تأیید شده است!", show_alert=True)

    if transaction.status == Transaction.Status.rejected:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        return await query.answer(
            "این فیش قبلاً رد شده و قابل تأیید مجدد نیست.",
            show_alert=True,
        )

    if transaction.status != Transaction.Status.waiting:
        await _sync_admin_receipt_messages(query.bot, transaction, query.message)
        return await query.answer(
            "وضعیت فعلی این تراکنش اجازه تأیید ندارد.", show_alert=True
        )

    updated = await _finish_waiting_transaction(transaction)
    transaction = await _load_card_to_card_transaction(transaction.id)
    if not transaction:
        return await query.answer("تراکنش یافت نشد!", show_alert=True)
    await _sync_admin_receipt_messages(query.bot, transaction, query.message)
    if not updated:
        return await query.answer(
            "وضعیت این فیش توسط ادمین دیگری تغییر کرده است.", show_alert=True
        )
    await query.answer("تراکنش تایید شد!", show_alert=True)
    text = f"""
✅ پرداخت شما از طریق کارت به کارت با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount - transaction.amount_free_given:,}</b> تومان
‌‌
"""
    msg = await query.bot.send_message(transaction.user_id, text=text)
    activate_service(transaction, msg)
