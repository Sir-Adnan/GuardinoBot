# ruff: noqa: E402

SETTINGS_KEY_PREFIX = "auto_select"

from enum import Enum

from app.plugins.payment.utils import Base


class SelectionAlgorithm(str, Enum):
    random = "random"
    least_vol = "least_vol"
    least_count = "least_count"
    most_vol = "most_vol"
    most_count = "most_count"


class Fields(str, Enum):
    enabled = "enabled"
    menu_title = "menu_title"

    algorithm = "algorithm"
    duration = "duration"
    payment_methods = "payment_methods"


class Settings(Base):
    class Config:
        from_attributes = True
        coerce_numbers_to_str = True

    _name = SETTINGS_KEY_PREFIX

    enabled: bool = False
    menu_title: str = "انتخاب خودکار درگاه"

    algorithm: SelectionAlgorithm = SelectionAlgorithm.random
    duration: int = 3
    _payment_methods: list[str] = [
        "payment_aqaye_pardakht",
        "payment_payping",
        "payment_zibal",
        "payment_zarinpal",
    ]
    payment_methods: list[str] = []

    _cached_provider: str | None = None
    _cached_provider_timestamp: float | None = None


from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.models.user import User
from app.utils import settings
from app.utils.filters import IsSuperUser

router = Router(name="payment/auto_select")


# # Admin settings Start
cancel_admin_form = CancelFormAdmin().as_markup(
    resize_keyboard=True, one_time_only=True
)


class SettingsKeyboard(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="set_auto_select"):
        field: Fields
        value: str | None = None
        confirmed: bool = False

    def __init__(
        self,
        _settings: "settings.Settings",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'فعال ✅' if _settings.payment_auto_select.enabled else 'غیرفعال ❌'}",
            callback_data=self.Callback(field=Fields.enabled),
        )
        self.button(
            text="ویرایش 'نام مستعار'",
            callback_data=self.Callback(field=Fields.menu_title),
        )
        self.button(
            text=f"الگوریتم: {_settings.payment_auto_select.algorithm.value}",
            callback_data=self.Callback(field=Fields.algorithm),
        )
        self.button(
            text=f"بازه زمانی محاسبه: {_settings.payment_auto_select.duration} روز",
            callback_data=self.Callback(field=Fields.duration),
        )
        methods = Settings._payment_methods.default
        for m in methods:
            self.button(
                text=f"{'✅' if m in _settings.payment_auto_select.payment_methods else '❌'} {m}",
                callback_data=self.Callback(field=Fields.payment_methods, value=m),
            )
        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
        )
        self.adjust(1, 1, 1)


class AutoSelectEditForm(StatesGroup):
    menu_title = State()
    duration = State()


@router.message(
    StateFilter(AutoSelectEditForm),
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
    _settings = settings.get_settings()
    text = f"""
نام درگاه: <b>{_settings.payment_auto_select.menu_title}</b>

این درگاه از بین درگاه‌های انتخاب شده توسط شما از لیست یکی را به صورت خودکار انتخاب کرده و پرداخت کاربر از طریق آن انجام می‌شود!

دقت کنید که در صورت فعال بودن این درگاه، درگاه‌های انتخاب شده به کاربر نمایش داده نخواهد شد و فقط این درگاه به کاربر نمایش داده می‌شود و پس از کلیک به صورت خودکار یک درگاه انتخاب می‌شود!


ملاک شمارش مقدار تراکنش‌های موفق می باشد!

# حالت‌های زیر برای انتخاب خودکار درگاه وجود دارند:

# random: یکی از درگاه‌ها به صورت تصادفی انتخاب می‌شود
# least_vol: درگاهی که کمترین حجم تراکنش را دارد انتخاب می‌شود
# least_count: درگاهی که کمترین تعداد تراکنش را دارد انتخاب می‌شود
# most_vol: درگاهی که بیشترین حجم تراکنش را دارد انتخاب می‌شود
# most_count: درگاهی که بیشترین تعداد تراکنش را دارد انتخاب می‌شود

# می‌توانید بازه زمانی برای محاسبه را تنظیم کنید.

دقت کنید که تنظیمات درگاه‌هایی که در این قسمت انتخاب میکنید باید به درستی انجام شده باشد و فعال باشند! در غیر این صورت کاربر با خطا روبرو خواهد شد!

راهنما: https://t.me/c/1921580752
"""

    markup = SettingsKeyboard(_settings=_settings).as_markup()

    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text=text, reply_markup=markup)
    return await qmsg.reply(text=text, reply_markup=markup)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.algorithm),
    IsSuperUser(),
)
async def cycle_algorihm(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_auto_select
    try:
        f = iter(SelectionAlgorithm)
        while next(f) != _settings.algorithm:
            pass
        _settings.algorithm = next(f)
    except StopIteration:
        _settings.algorithm = next(iter(SelectionAlgorithm))  # get first enum value

    text = f"الگوریتم انتخاب درگاه به {_settings.algorithm.value} تنظیم شد!"
    _settings._cached_provider = None
    await settings.Settings.update(payment_auto_select=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.payment_methods),
    IsSuperUser(),
)
async def cycle_methods(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_auto_select
    if callback_data.value in _settings.payment_methods:
        _settings.payment_methods.remove(callback_data.value)
    else:
        _settings.payment_methods.append(callback_data.value)
    _settings._cached_provider = None
    await settings.Settings.update(payment_auto_select=_settings)
    await settings.reload_settings()
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.enabled),
    IsSuperUser(),
)
async def edit_settings(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings().payment_auto_select
    if _settings.enabled:
        _settings.enabled = False
        text = "درگاه انتخاب خودکار غیرفعال شد!"
    else:
        _settings.enabled = True
        text = "درگاه انتخاب خودکار فعال شد!"
    _settings._cached_provider = None
    await settings.Settings.update(payment_auto_select=_settings)
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.menu_title),
    IsSuperUser(),
)
async def edit_menu_title(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    await state.set_state(AutoSelectEditForm.menu_title)
    await query.message.answer(
        "مقدار جدید نام مستعار درگاه را وارد کنید:",
        reply_markup=cancel_admin_form,
    )


@router.message(
    AutoSelectEditForm.menu_title,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_menu_title(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings().payment_auto_select
    menu_title = message.text.strip().replace("\n", " ")
    origv = _settings.menu_title
    _settings.menu_title = menu_title
    await settings.Settings.update(payment_auto_select=_settings)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{menu_title}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await show_settings(message, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.field == Fields.duration),
    IsSuperUser(),
)
async def edit_auto_select_duration(  # noqa: F811
    query: CallbackQuery,
    user: User,
    callback_data: SettingsKeyboard.Callback,
    state: FSMContext,
):
    await state.set_state(AutoSelectEditForm.duration)
    await query.message.answer(
        "تراکنش‌های چند روز قبل برای محاسبه استفاده شوند؟",
        reply_markup=cancel_admin_form,
    )


@router.message(
    AutoSelectEditForm.duration,
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def get_duration(message: Message, user: User, state: FSMContext):  # noqa: F811
    duration = message.text.strip()
    try:
        duration = int(duration)
    except ValueError:
        return await message.answer("لطفا مقداری عددی وارد کنید:")

    if duration < 1:
        return await message.answer("مقدار باید بیشتر از ۱ باشد!")

    _settings = settings.get_settings().payment_auto_select
    _settings.duration = duration
    _settings._cached_provider = None
    await settings.Settings.update(payment_auto_select=_settings)
    await settings.reload_settings()
    await state.clear()
    await message.answer("مقدار با موفقیت ویرایش شد!", show_alert=True)
    await show_settings(message, user)


# # User handlers Start
