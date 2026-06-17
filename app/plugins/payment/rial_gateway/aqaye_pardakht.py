# ruff: noqa: E402


SETTINGS_KEY_PREFIX = "aqaye_pardakht"


from enum import Enum
from typing import Any, Callable

from app.plugins.payment.utils import BaseSettings, BaseTexts
from app.utils.values import TextValue, format_number


class Fields(str, Enum):
    enabled = "enabled"
    min_pay_amount = "min_pay_amount"
    free_after = "free_after"
    free_after_percent = "free_after_percent"
    menu_title = "menu_title"

    api_key = "api_key"

    text_choose_amount = "text_choose_amount"
    text_show_invoice = "text_show_invoice"


class Settings(BaseSettings):
    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "درگاه ریالی aqaye_pardakht"

    api_key: str | None = None


class ChooseAmountText(TextValue):
    value: str = """
✔️ شما در حال افزایش اعتبار با {PAYMENT_PROVIDER_TITLE} هستید!

❗️اگر اشتباه وارد این بخش شدید دکمه «برگشت» را کلیک کنید
~~~~~~~~~~~~~~~~~~~~~~~~
✔️ برای ادامه، مبلغ مورد نظر برای افزایش اعتبار رو انتخاب کنید:
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": str,
        "MINIMUM_PAY_AMOUNT": int,
    }


class ShowInvoiceText(TextValue):
    value: str = """
✅ فاکتور افزایش اعتبار شما ساخته شد!

💳 شماره فاکتور: {TRANSACTION_ID}
💲مبلغ قابل پرداخت: <b>{AMOUNT_TOMAN}</b> تومان
🚦درگاه پرداخت: <b>{PAYMENT_PROVIDER_TITLE}</b>
~~~~~~~~~~~~~~~~~~~~~~~~
⚠️ فاکتور پرداخت شما تا ۲ ساعت دیگر معتبر می‌باشد.

🟩 برای پرداخت روی دکمه زیر کلیک کنید:
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": lambda v: v,
        "MINIMUM_PAY_AMOUNT": format_number,
        "TRANSACTION_ID": format_number,
        "AMOUNT_TOMAN": format_number,
        "AMOUNT_RIAL": format_number,
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

from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.user import payment
from app.models.user import Invoice, RialGatewayPayment, Transaction, User
from app.utils import settings, texts
from app.utils.filters import IsSuperUser
from app.utils.values import admin_edit_texts_format, check_texts

from .clients import AqayePardakhtAPI, GatewayError

router = Router(name="payment/aqaye_pardakht")


# # Admin settings Start
cancel_admin_form = CancelFormAdmin().as_markup(
    resize_keyboard=True, one_time_only=True
)


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="set_aqaye_pardakht"):
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
    class Callback(CallbackData, prefix="txt_aqaye_pardakht"):
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


class PayUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="💳 پرداخت", url=url)


class AqayePardakhtEditForm(StatesGroup):
    api_key = State()
    menu_title = State()
    min_pay_amount = State()

    free_after = State()
    free_after_percent = State()

    text_choose_amount = State()
    text_show_invoice = State()


class AqayePardakhtCustomAmountForm(StatesGroup):
    method = State()
    amount = State()


@router.message(
    StateFilter(AqayePardakhtEditForm),
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
    _settings = settings.get_settings().payment_aqaye_pardakht
    text = f"""
API Key: <code>{_settings.api_key}</code>

نام مستعار: <b>{_settings.menu_title}</b>

حداقل مبلغ قابل پرداخت: <code>{_settings.min_pay_amount}</code>

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
    _settings = settings.get_settings().payment_aqaye_pardakht
    if _settings.enabled:
        _settings.enabled = False
        text = "درگاه aqaye_pardakht غیرفعال شد!"
    else:
        _settings.enabled = True
        text = "درگاه aqaye_pardakht فعال شد!"
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
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
        ed_text = _texts.payment_aqaye_pardakht.choose_amount
    elif callback_data.field == Fields.text_show_invoice:
        ed_text = _texts.payment_aqaye_pardakht.show_invoice
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
    _texts = texts.get_texts().payment_aqaye_pardakht
    if callback_data.field == Fields.text_choose_amount:
        _texts.choose_amount = ChooseAmountText()
    elif callback_data.field == Fields.text_show_invoice:
        _texts.show_invoice = ShowInvoiceText()
    else:
        return await query.answer(
            f"بازنشانی متن برای {callback_data.field.name} تعریف نشده است!"
        )
    await texts.Texts.update(payment_aqaye_pardakht=_texts)
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
        await state.set_state(AqayePardakhtEditForm.text_choose_amount)
    elif callback_data.field == Fields.text_show_invoice:
        await state.set_state(AqayePardakhtEditForm.text_show_invoice)
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
    AqayePardakhtEditForm.text_choose_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts().payment_aqaye_pardakht

    if not await check_texts(_texts.choose_amount, message):
        return
    _texts.choose_amount = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_aqaye_pardakht=_texts)
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
    AqayePardakhtEditForm.text_show_invoice,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts().payment_aqaye_pardakht

    if not await check_texts(_texts.choose_amount, message):
        return
    _texts.choose_amount = ChooseAmountText(value=message.text)
    await texts.Texts.update(payment_aqaye_pardakht=_texts)
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
    _settings = settings.get_settings().payment_aqaye_pardakht
    if callback_data.field == Fields.api_key:
        text = "مقدار جدید API key را وارد کنید: (برای عدم تنظیم <code>0</code> را وارد کنید)"
        await state.set_state(AqayePardakhtEditForm.api_key)

    elif callback_data.field == Fields.min_pay_amount:
        text = "مقدار جدید حداقل مبلغ قابل پرداخت را به تومان وارد کنید:"
        await state.set_state(AqayePardakhtEditForm.min_pay_amount)

    elif callback_data.field == Fields.menu_title:
        text = "مقدار جدید نام مستعار را وارد کنید:"
        await state.set_state(AqayePardakhtEditForm.menu_title)

    elif callback_data.field == Fields.free_after:
        text = f"تراکنش‌ها از چه مبلغی به بعد شامل {_settings.free_after_percent} درصد اعتبار هدیه شوند؟ برای غیرفعال سازی 0 را وارد کنید:"
        await state.set_state(AqayePardakhtEditForm.free_after)

    elif callback_data.field == Fields.free_after_percent:
        if not _settings.free_after:
            return await query.answer(
                "ابتدا اعتبار هدیه را فعال کرده و سپس درصد را تنظیم کنید!"
            )
        text = f"تراکنش‌های بیشتر از {_settings.free_after:,} شامل چند درصد اعتبار هدیه شوند؟"
        await state.set_state(AqayePardakhtEditForm.free_after_percent)
    else:
        return await query.answer(
            f"تنظیمات برای {callback_data.field.value} تعریف نشده است!", show_alert=True
        )
    await query.message.reply(
        text=text,
        reply_markup=cancel_admin_form,
    )


@router.message(
    AqayePardakhtEditForm.api_key,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_api_key(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_aqaye_pardakht
    api_key = message.text.strip()
    if api_key == "0":
        api_key = None
    origv = _settings.api_key
    _settings.api_key = api_key
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{api_key}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    AqayePardakhtEditForm.menu_title,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_menu_title(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_aqaye_pardakht
    menu_title = message.text.strip().replace("\n", " ")
    origv = _settings.menu_title
    _settings.menu_title = menu_title
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
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
    AqayePardakhtEditForm.min_pay_amount,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_min_pay_amount(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_aqaye_pardakht
    try:
        min_pay_amount = int(message.text)
    except ValueError:
        return await message.reply(
            f"{message.text} مقداری نامعتبر است! لطفا مقداری عددی وارد کنید:"
        )
    origv = _settings.min_pay_amount
    _settings.min_pay_amount = min_pay_amount
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
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
    AqayePardakhtEditForm.free_after,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_aqaye_pardakht
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
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
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
    AqayePardakhtEditForm.free_after_percent,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after_percent(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_aqaye_pardakht
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
    await settings.Settings.update(payment_aqaye_pardakht=_settings)
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
    StateFilter(AqayePardakhtCustomAmountForm),
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
    if not _settings.payment_aqaye_pardakht.enabled:
        text = f"🚫 در حال حاضر امکان پرداخت به وسیله {_settings.payment_aqaye_pardakht.menu_title} غیرفعال می‌باشد!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text=text, show_alert=True)
        return await qmsg.answer(text=text)
    _texts = texts.get_texts().payment_aqaye_pardakht
    text = texts.Texts.format(
        _texts.choose_amount,
        PAYMENT_PROVIDER_TITLE=_settings.payment_aqaye_pardakht.menu_title,
        MINIMUM_PAY_AMOUNT=_settings.payment_aqaye_pardakht.min_pay_amount,
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
    await state.set_state(AqayePardakhtCustomAmountForm.amount)
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
    AqayePardakhtCustomAmountForm.amount,
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
    _settings = settings.get_settings().payment_aqaye_pardakht
    if not _settings.enabled:
        text = f"🚫 در حال حاضر امکان پرداخت به وسیله {_settings.menu_title} غیرفعال می‌باشد!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text=text, show_alert=True)
        return await qmsg.answer(text=text)
    await qmsg.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        # TODO: rewrite callback-url and pay_url
        async with in_transaction():
            transaction = await Transaction.create(
                type=Transaction.PaymentType.rial_gateway,
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
            payment = await AqayePardakhtAPI.create(
                amount=callback_data.amount,
                transaction_id=transaction.id,
                description=f"origin={(await qmsg.bot.me()).id},order_id={transaction.id},user_id={user.id}",
            )
            await RialGatewayPayment.create(
                provider=RialGatewayPayment.Provider.aqaye_pardakht,
                data=payment.model_dump(mode="json"),
                transaction=transaction,
            )
        _texts = texts.get_texts().payment_aqaye_pardakht
        text = texts.Texts.format(
            _texts.show_invoice,
            PAYMENT_PROVIDER_TITLE=_settings.menu_title,
            TRANSACTION_ID=transaction.id,
            AMOUNT_TOMAN=transaction.amount - transaction.amount_free_given,
        )
        markup = PayUrl(
            url=payment.url,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text=text, reply_markup=markup)
        return await qmsg.answer(text=text, reply_markup=markup)
    except GatewayError as err:
        text = f"📍 درحال حاضر امکان پرداخت از طریق {_settings.menu_title} وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text=text, show_alert=True)
        else:
            await qmsg.answer(text=text)
        raise err
