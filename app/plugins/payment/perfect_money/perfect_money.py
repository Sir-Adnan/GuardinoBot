# ruff: noqa: E402


SETTINGS_KEY_PREFIX = "perfect_money"


from enum import Enum
from typing import Any, Callable

from app.plugins.payment.utils import BaseSettings, BaseTexts
from app.utils.values import TextValue


class Fields(str, Enum):
    enabled = "enabled"
    free_after = "free_after"
    free_after_percent = "free_after_percent"
    menu_title = "menu_title"

    account_id = "account_id"
    payee_account = "payee_account"
    passphrase = "passphrase"
    test = "test"

    text_show_info = "text_show_info"


class Settings(BaseSettings):
    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "💵 ووچر پرفکت‌مانی"
    is_voucher: bool = True

    account_id: str | None = None
    payee_account: str | None = None
    passphrase: str | None = None


class ShowInfoText(TextValue):
    value: str = """
💡 یکی از روش‌های امن و راحت شارژ حساب استفاده از ووچر پرفکت‌مانی هست
~~~~~~~~~~~~~~~~~~~~~~~~
⁉️ برای خرید ووچر پرفکت مانی میتونید از سایت‌های واسطه مثل 👇
🔗 xpayex.com
🔗 weswap.digital
🔗 nikpardakht.com
یا هر سایت دیگه‌ای که خودتون میشناسید استفاده کنید😉

❗️فقط ووچرهای خریداری شده با پایه ارزی دلار (USD) پذیرفته خواهند شد و مسئولیت ووچرهای خریداری شده با پایه ارزی دیگر با خود کاربر می‌باشد

⁉️ توجه کنید که مقدار ریالی ووچر خریداری شده با نرخ لحظه‌ای دلار وقتی که دکمه ارسال رو میزنید حساب میشه

⁉️ توجه کنید که تیم ما هیچ مسئولیتی بابت سایت‌های معرفی شده ندارد و خرید از این سایت‌ها با مسئولیت خود شما می‌باشد⚠️
~~~~~~~~~~~~~~~~~~~~~~~~
💲 نرخ این لحظه دلار: {USDT_RATE} تومان
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "PAYMENT_PROVIDER_TITLE": str,
        "USDT_RATE": float,
    }


class Texts(BaseTexts):
    show_info: ShowInfoText = ShowInfoText()


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

from app.handlers import base as base_handlers
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.user import account, payment
from app.models.user import PerfectMoneyPayment, Transaction, User
from app.plugins.payment.clients import CouldNotGetUSDTPrice, NobitexMarketAPI
from app.utils import helpers, settings, texts
from app.utils.filters import IsSuperUser
from app.utils.values import admin_edit_texts_format, check_texts

from .clients import PerfectMoneyAPI, PerfectMoneyError

router = Router(name="payment/perfect_money")


# # Admin settings Start
cancel_admin_form = CancelFormAdmin().as_markup(
    resize_keyboard=True, one_time_only=True
)


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="set_perfect_money"):
        field: Fields
        confirmed: bool = False

    def __init__(self, settings: Settings, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'فعال ✅' if settings.enabled else 'غیرفعال ❌'}",
            callback_data=self.Callback(field=Fields.enabled),
        )
        self.button(
            text="ویرایش 'Account ID'",
            callback_data=self.Callback(field=Fields.account_id),
        )
        self.button(
            text="ویرایش 'Payee Account'",
            callback_data=self.Callback(field=Fields.payee_account),
        )
        self.button(
            text="ویرایش 'Passphrase'",
            callback_data=self.Callback(field=Fields.passphrase),
        )
        self.button(
            text="بررسی اتصال",
            callback_data=self.Callback(field=Fields.test),
        )
        self.button(
            text="ویرایش 'نام مستعار'",
            callback_data=self.Callback(field=Fields.menu_title),
        )
        self.button(
            text="ویرایش متن 'توضیحات'",
            callback_data=self.Callback(field=Fields.text_show_info),
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
    class Callback(CallbackData, prefix="txt_perfect_money"):
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


class EnterPerfectMoney(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="entrprfctmn"):
        pass

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="✍️ ارسال کد", callback_data=self.Callback())
        self.button(
            text="🔙 برگشت",
            callback_data=account.UserPanel.Callback(
                action=account.UserPanelAction.charge
            ),
        )
        self.adjust(1, 1)


class PerfectMoneyEditForm(StatesGroup):
    account_id = State()
    payee_account = State()
    passphrase = State()
    menu_title = State()
    min_pay_amount = State()

    free_after = State()
    free_after_percent = State()

    text_show_info = State()


class ActivatePMVoucher(StatesGroup):
    ev_number = State()
    ev_code = State()


@router.message(
    StateFilter(PerfectMoneyEditForm),
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
    _settings = settings.get_settings().payment_perfect_money
    text = f"""
Account ID: <code>{_settings.account_id}</code>
Payee Account: <code>{_settings.payee_account}</code>
Passphrase: <code>{_settings.passphrase}</code>

نام مستعار: <b>{_settings.menu_title}</b>

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
    _settings = settings.get_settings().payment_perfect_money
    if _settings.enabled:
        _settings.enabled = False
        text = "درگاه perfect_money غیرفعال شد!"
    else:
        _settings.enabled = True
        text = "درگاه perfect_money فعال شد!"
    await settings.Settings.update(payment_perfect_money=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field.in_([Fields.text_show_info])),
    IsSuperUser(),
)
async def edit_settings_texts(
    qmsg: CallbackQuery | Message, user: User, callback_data: SettingsKeyboard.Callback
):
    _texts = texts.get_texts()
    ed_text = None
    if callback_data.field == Fields.text_show_info:
        ed_text = _texts.payment_perfect_money.show_info
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
    _texts = texts.get_texts().payment_perfect_money
    if callback_data.field == Fields.text_show_info:
        _texts.show_info = ShowInfoText()
    else:
        return await query.answer(
            f"بازنشانی متن برای {callback_data.field.name} تعریف نشده است!"
        )
    await texts.Texts.update(payment_perfect_money=_texts)
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
    if callback_data.field == Fields.text_show_info:
        await state.set_state(PerfectMoneyEditForm.text_show_info)
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
    PerfectMoneyEditForm.text_show_info,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts().payment_perfect_money

    if not await check_texts(_texts.show_info, message):
        return
    _texts.show_info = ShowInfoText(value=message.text)
    await texts.Texts.update(payment_perfect_money=_texts)
    await texts.reload_texts()
    text = f"""
متن show_info با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsKeyboard.Callback(field=Fields.text_show_info),
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(~F.field.in_([Fields.test])), IsSuperUser()
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings().payment_perfect_money
    if callback_data.field == Fields.account_id:
        text = "مقدار جدید Account ID را وارد کنید: (برای عدم تنظیم <code>0</code> را وارد کنید)"
        await state.set_state(PerfectMoneyEditForm.account_id)
    elif callback_data.field == Fields.payee_account:
        text = "مقدار جدید Payee Account را وارد کنید: (برای عدم تنظیم <code>0</code> را وارد کنید)"
        await state.set_state(PerfectMoneyEditForm.payee_account)
    elif callback_data.field == Fields.passphrase:
        text = "مقدار جدید Passphrase را وارد کنید: (برای عدم تنظیم <code>0</code> را وارد کنید)"
        await state.set_state(PerfectMoneyEditForm.passphrase)
    elif callback_data.field == Fields.menu_title:
        text = "مقدار جدید نام مستعار را وارد کنید:"
        await state.set_state(PerfectMoneyEditForm.menu_title)

    elif callback_data.field == Fields.free_after:
        text = f"تراکنش‌ها از چه مبلغی به بعد شامل {_settings.free_after_percent} درصد اعتبار هدیه شوند؟ برای غیرفعال سازی 0 را وارد کنید:"
        await state.set_state(PerfectMoneyEditForm.free_after)

    elif callback_data.field == Fields.free_after_percent:
        if not _settings.free_after:
            return await query.answer(
                "ابتدا اعتبار هدیه را فعال کرده و سپس درصد را تنظیم کنید!"
            )
        text = f"تراکنش‌های بیشتر از {_settings.free_after:,} شامل چند درصد اعتبار هدیه شوند؟"
        await state.set_state(PerfectMoneyEditForm.free_after_percent)
    else:
        return await query.answer(
            f"تنظیمات برای {callback_data.field.value} تعریف نشده است!", show_alert=True
        )
    await query.message.reply(
        text=text,
        reply_markup=cancel_admin_form,
    )


@router.message(
    PerfectMoneyEditForm.account_id,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_account_id(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
    account_id = message.text.strip()
    if account_id == "0":
        account_id = None
    else:
        try:
            account_id = int(account_id)
        except ValueError:
            return await message.reply(
                f"{account_id} مقداری عددی نیست! دوباره تلاش کنید:"
            )
    origv = _settings.account_id
    _settings.account_id = account_id
    await settings.Settings.update(payment_perfect_money=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{account_id}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    PerfectMoneyEditForm.payee_account,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_payee_account(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
    payee_account = message.text.strip()
    if payee_account == "0":
        payee_account = None
    else:
        if not payee_account.startswith("U"):
            return await message.reply(
                f"{payee_account} مقداری نامعتبر است! مقدار باید با <b>U</b> شروع شود. دوباره تلاش کنید:"
            )
    origv = _settings.payee_account
    _settings.payee_account = payee_account
    await settings.Settings.update(payment_perfect_money=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{payee_account}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.message(
    PerfectMoneyEditForm.passphrase,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_passphrase(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
    passphrase = message.text.strip()
    if passphrase == "0":
        passphrase = None
    origv = _settings.passphrase
    _settings.passphrase = passphrase
    await settings.Settings.update(payment_perfect_money=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{passphrase}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field.in_([Fields.test])), IsSuperUser()
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings().payment_perfect_money
    if _settings.account_id is None:
        return await query.answer("مقدار 'Account ID' تنظیم نشده است!", show_alert=True)
    elif _settings.payee_account is None:
        return await query.answer(
            "مقدار 'Payee Account' تنظیم نشده است!", show_alert=True
        )
    elif _settings.passphrase is None:
        return await query.answer("مقدار 'Passphrase' تنظیم نشده است!", show_alert=True)
    try:
        await PerfectMoneyAPI.ev_activate(
            ev_number="1234", ev_code="6543"
        )  # some random entry
    except PerfectMoneyError as exc:
        if str(exc).startswith("Can not login with") or str(exc).startswith(
            "Invalid Payee_Account"
        ):
            await query.answer(f"اتصال ناموفق!\nخطا: {exc}", show_alert=True)
            raise exc
    await query.answer("اتصال موفق!", show_alert=True)


@router.message(
    PerfectMoneyEditForm.menu_title,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_menu_title(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
    menu_title = message.text.strip().replace("\n", " ")
    origv = _settings.menu_title
    _settings.menu_title = menu_title
    await settings.Settings.update(payment_perfect_money=_settings)
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
    PerfectMoneyEditForm.free_after,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
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
    await settings.Settings.update(payment_perfect_money=_settings)
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
    PerfectMoneyEditForm.free_after_percent,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_free_after_percent(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money
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
    await settings.Settings.update(payment_perfect_money=_settings)
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
    StateFilter(ActivatePMVoucher),
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
    _settings = settings.get_settings().payment_perfect_money

    if not _settings.enabled or any(
        [
            _settings.account_id is None,
            _settings.passphrase is None,
            _settings.payee_account is None,
        ]
    ):
        text = f"🚫 در حال حاضر امکان پرداخت به وسیله {_settings.menu_title} غیرفعال می‌باشد!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                text=text,
                show_alert=True,
            )
        return await qmsg.answer(
            text=text,
        )
    try:
        usdt_rate = await NobitexMarketAPI.get_price()
        _texts = texts.get_texts().payment_perfect_money
        text = texts.Texts.format(
            _texts.show_info,
            PAYMENT_PROVIDER_TITLE=_settings.menu_title,
            USDT_RATE=usdt_rate,
        )
        markup = EnterPerfectMoney().as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=markup,
            )
        return await qmsg.answer(
            text,
            reply_markup=markup,
        )
    except CouldNotGetUSDTPrice as err:
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


@router.callback_query(EnterPerfectMoney.Callback.filter())
async def perfectmoney_method_send(query: CallbackQuery, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_perfect_money

    if not _settings.enabled or any(
        [
            _settings.account_id is None,
            _settings.passphrase is None,
            _settings.payee_account is None,
        ]
    ):
        text = f"🚫 در حال حاضر امکان پرداخت به وسیله {_settings.menu_title} غیرفعال می‌باشد!"
        return await query.answer(
            text=text,
        )
    text = f"💳 کد ووچر(EV Number) پرفکت‌مانی را ارسال کنید: (برای لغو دکمه «{base.MainMenu.back}» رو کلیک کنید)"
    await state.set_state(ActivatePMVoucher.ev_number)
    await query.message.reply(
        text,
        reply_markup=base.CancelUserForm().as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )


@router.message(ActivatePMVoucher.ev_number)
async def perfect_money_get_evnumber(message: Message, user: User, state: FSMContext):
    text = f"💳 کد فعال‌سازی ووچر(EV Code) پرفکت‌مانی را ارسال کنید: (برای لغو دکمه «{base.MainMenu.back}» رو کلیک کنید)"
    if not message.text.isnumeric():
        return await message.answer("❌ فرمت کد ارسالی نادرست است! دوباره ارسال کنید:")
    await state.update_data(ev_number=message.text)
    await state.set_state(ActivatePMVoucher.ev_code)
    await message.answer(
        text,
        reply_markup=base.CancelUserForm().as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )


@router.message(ActivatePMVoucher.ev_code)
async def perfect_money_get_evcode(message: Message, user: User, state: FSMContext):
    if not message.text.isnumeric():
        return await message.answer("❌ فرمت کد ارسالی نادرست است! دوباره ارسال کنید:")
    await message.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        result = await PerfectMoneyAPI.ev_activate(
            ev_number=(await state.get_data()).get("ev_number"), ev_code=message.text
        )
    except PerfectMoneyError as err:
        if str(
            err
        ) == "No response returned" or "Can not login with passed AccountID" in str(
            err
        ):
            await state.clear()
            await message.answer(
                "📍 خطایی در روند تأیید رخ داد! لطفا با پشتیبانی تماس بگیرید."
            )
            await base.main_menu_handler(message, user)
            raise err
        await message.answer("❌ کد ارسالی قبلا استفاده شده یا نامعتبر است!")
        await base_handlers.main_menu_handler(message, user)
        raise err

    ev_number = result.get("VOUCHER_NUM")
    ev_amount = result.get("VOUCHER_AMOUNT")
    ev_amount_currency = result.get("VOUCHER_AMOUNT_CURRENCY")
    payee_account = result.get("Payee_Account")
    payment_batch_number = result.get("PAYMENT_BATCH_NUM")

    await state.clear()
    _settings = settings.get_settings().payment_perfect_money
    try:
        async with in_transaction():
            usd_rate = await NobitexMarketAPI.get_price()
            amount = usd_rate * float(ev_amount)
            free = (
                0
                if (not _settings.free_after) or (amount < _settings.free_after)
                else amount * (_settings.free_after_percent / 100)
            )
            transaction = await Transaction.create(
                type=Transaction.PaymentType.perfectmoney,
                status=Transaction.Status.finished,
                amount=amount + free,
                amount_free_given=free,
                user=user,
            )
            payment = await PerfectMoneyPayment.create(
                usd_rate=usd_rate,
                payee_account=payee_account,
                ev_number=ev_number,
                ev_code=message.text,
                ev_amount_currency=ev_amount_currency,
                payment_batch_number=payment_batch_number,
                transaction=transaction,
            )
            text = f"""
✅ پرداخت شما با موفقیت تأیید شد

🤑 مبلغ {amount} تومان{f' + ({free}) 🔥 اعتبار هدیه' if free > 0 else ''} به اعتبار حساب شما اضافه شد
"""
            await message.answer(
                text,
            )
            await transaction.refresh_from_db()
            helpers.transaction_log(transaction=transaction, payment=payment)
    except Exception as err:
        text = """
❌ عملیات با خطا مواجه شد!
اگر از صحت اطلاعات وارد شده اطمینان دارید، لطفا با پشتیبانی تماس بگیرید.
    """
        await message.answer(text)
        raise err
    await base_handlers.main_menu_handler(message, user)
