import re
from itertools import chain

from aiogram import F, exceptions
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.handlers.user.account import ACCOUNT_TYPE
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.admin.setting import (
    USERNAME_GENERATORS,
    ConfirmKeyboard,
    ConfirmPayAmountSettings,
    ConfirmSettings,
    MSettings,
    MSettingsActions,
    PayAmountSetting,
    PayAmountSettingActions,
    ReportsConfirm,
    ReportsSettings,
    ReportsSettingsActions,
    SettingsActions,
    SettingsKeyboard,
    SettingsMisc,
    SettingsTexts,
    SettingsTextsActions,
    SettingsTextsEdit,
)
from app.main import bot
from app.models.user import User
from app.utils import helpers, reports, settings, texts
from app.utils.filters import IsSuperUser
from app.utils.values import admin_edit_texts_format, check_texts

from . import router

cancel_form = CancelFormAdmin().as_markup(resize_keyboard=True, one_time_only=True)


@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.settings), IsSuperUser()
)
async def show_settings(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext | None = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="Canceled!", reply_markup=ReplyKeyboardRemove())

    reply_markup = SettingsKeyboard(_settings=settings.get_settings()).as_markup()
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text("Settings:", reply_markup=reply_markup)
    return await query.answer("Settings:", reply_markup=reply_markup)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.flip_access_only),
    IsSuperUser(),
)
async def edit_settings(
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().access_only
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
حالت دسترسی فقط با دعوت فعال شود؟ 
(سیستم زیرمجموعه گیری به طور خوکار غیرفعال می‌شود)

note: ❗️❗️<strong>فقط کسانی که توسط ادمین‌ها دعوت شوند قادر به استفاده هستند</strong>
            """
        else:
            text = """
حالت دسترسی فقط با دعوت غیرفعال شود؟ 

note: ❗️❗️<strong>فقط کسانی که توسط ادمین‌ها دعوت شوند قادر به استفاده هستند</strong>
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_access_only,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(access_only=False)
        text = "حالت دسترسی فقط با دعوت غیرفعال شد!"
    else:
        await settings.Settings.update(access_only=True, referral_system=False)
        text = "حالت دسترسی فقط با دعوت فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.flip_referral_system),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().referral_system
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
سیستم زیرمجموعه گیری فعال شود؟

note: ❗️❗️<strong>کاربران می‌توانند با دعوت دیگران تخفیف بگیرند</strong>
            """
        else:
            text = """
سیستم زیرمجموعه گیری غیرفعال شود؟

note: ❗️❗️<strong>کاربران می‌توانند با دعوت دیگران تخفیف بگیرند</strong>
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_referral_system,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(referral_system=False)
        text = "سیستم زیرمجموعه گیری غیرفعال شد!"
    else:
        await settings.Settings.update(referral_system=True)
        text = "سیستم زیرمجموعه گیری فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.flip_phone_number_verify
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().phone_number_verify
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
تأیید شماره موبایل فعال شود؟

note: ❗️❗️<strong>کاربران برای استفاده از ربات باید شماره موبایل «ایران» خود را به اشتراک بگذارند</strong>
            """
        else:
            text = """
تأیید شماره موبایل غیرفعال شود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_phone_number_verify,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(phone_number_verify=False)
        text = "تأیید شماره موبایل غیرفعال شد!"
    else:
        await settings.Settings.update(phone_number_verify=True)
        text = "تأیید شماره موبایل فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.flip_reset_password_button
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().reset_password_button
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
دکمه تغییر پسوورد در پنل پروکسی‌ها نمایش داده شود؟
            """
        else:
            text = """
دکمه تغییر پسوورد در پنل پروکسی‌ها نمایش داده نشود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_reset_password_button,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(reset_password_button=False)
        text = "دکمه تغییر پسوورد غیرفعال شد!"
    else:
        await settings.Settings.update(reset_password_button=True)
        text = "دکمه تغییر پسوورد فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.flip_show_connect_links_button
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().show_connect_links_button
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
دکمه "نمایش لینک‌های اتصال" در پنل پروکسی‌ها نمایش داده شود؟
            """
        else:
            text = """
دکمه "نمایش لینک‌های اتصال" در پنل پروکسی‌ها نمایش داده نشود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_show_connect_links_button,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(show_connect_links_button=False)
        text = "دکمه نمایش لینک‌های اتصال غیرفعال شد!"
    else:
        await settings.Settings.update(show_connect_links_button=True)
        text = "دکمه نمایش لینک‌های اتصال فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(query, user)


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.flip_show_test_service_in_menu
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    status = settings.get_settings().show_test_service_in_menu
    if not callback_data.confirmed:
        await query.answer()
        if not status:
            text = """
سرویس‌های تست در منوی اصلی نمایش داده شوند؟
            """
        else:
            text = """
سرویس‌های تست در منوی اصلی نمایش داده نشوند؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmSettings(
                action=SettingsActions.flip_show_test_service_in_menu,
            ).as_markup(),
        )
    if status:
        await settings.Settings.update(show_test_service_in_menu=False)
        text = "نمایش سرویس‌های تست در منوی اصلی غیرفعال شد!"
    else:
        await settings.Settings.update(show_test_service_in_menu=True)
        text = "نمایش سرویس‌های تست در منوی اصلی فعال شد!"
    await settings.reload_settings()
    await query.answer(text, show_alert=True)
    await show_settings(
        query,
        user,
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.cycle_disable_users_role
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings()
    role = _settings.disable_users_role
    try:
        f = iter(User.Role)
        while next(f) != role:
            pass
        role = next(f)
    except StopIteration:
        role = next(iter(User.Role))  # get first enum value

    await settings.Settings.update(disable_users_role=role)
    await settings.reload_settings()
    await query.answer(
        f"سطح دسترسی غیرفعال سازی موقت به بالاتر از {ACCOUNT_TYPE.get(role.name)} تغییر کرد!",
        show_alert=True,
    )
    await show_settings(
        query,
        user,
    )


@router.callback_query(
    SettingsKeyboard.Callback.filter(
        F.action == SettingsActions.cycle_username_generator
    ),
    IsSuperUser(),
)
async def edit_settings(  # noqa: F811
    query: CallbackQuery, user: User, callback_data: SettingsKeyboard.Callback
):
    _settings = settings.get_settings()
    generator = _settings.username_generator
    try:
        f = iter(settings.UsernameGenerators)
        while next(f) != generator:
            pass
        generator = next(f)
    except StopIteration:
        generator = next(iter(settings.UsernameGenerators))  # get first enum value

    await settings.Settings.update(username_generator=generator)
    await settings.reload_settings()
    await query.answer(
        f"نحوه انتخاب نام اشتراک به {USERNAME_GENERATORS.get(generator)} تغییر کرد!",
        show_alert=True,
    )
    await show_settings(
        query,
        user,
    )


class EditMiscForm(StatesGroup):
    username_prefix = State()
    daily_test_services = State()
    on_hold_timeout_seconds = State()
    delete_expired_users_after_days = State()
    transaction_logs = State()
    orders_logs = State()
    referral_discount_percent = State()
    cancel_payback_fee = State()
    cancel_payback_days = State()
    marzban_webhook_secret = State()
    force_join_chats = State()
    remind_invoices_each_n_days = State()
    remind_invoices_after_amount = State()


@router.callback_query(
    MSettings.Callback.filter(F.action.name.startswith("edit_")),
    IsSuperUser(),
)
async def edit_settings_all(
    query: CallbackQuery,
    user: User,
    callback_data: MSettings.Callback,
    state: FSMContext,
):
    if callback_data.action == MSettingsActions.edit_default_username_prefix:
        text = "مقدار جدید Username Prefix را وارد کنید:"
        await state.set_state(EditMiscForm.username_prefix)

    elif callback_data.action == MSettingsActions.edit_default_daily_test_services:
        text = "مقدار جدید Daily Test Services را وارد کنید:"
        await state.set_state(EditMiscForm.daily_test_services)

    elif callback_data.action == MSettingsActions.edit_on_hold_timeout_seconds:
        text = """
مقدار جدید مدت زمان مجاز شروع از اولین اتصال را به فرمت زیر وارد کنید:
^[0-9]{1,3}(D|H)

مثال:
18h -> ۱۸ ساعت
3d -> سه روز
"""
        await state.set_state(EditMiscForm.on_hold_timeout_seconds)

    elif callback_data.action == MSettingsActions.edit_delete_expired_users_after_days:
        text = """
اشتراک‌های منقضی شده بعد از چند روز از تمدید نشدن به صورت خودکار حذف شوند؟ (برای حذف نشدن 0 را وارد کنید)
"""
        await state.set_state(EditMiscForm.delete_expired_users_after_days)
    elif callback_data.action == MSettingsActions.edit_referral_discount_percent:
        text = "مقدار جدید Referral Discount percent را وارد کنید:"
        await state.set_state(EditMiscForm.referral_discount_percent)

    elif callback_data.action == MSettingsActions.edit_cancel_payback_fee:
        text = "مقدار جدید Cancel Payback Fee را وارد کنید:"
        await state.set_state(EditMiscForm.cancel_payback_fee)

    elif callback_data.action == MSettingsActions.edit_cancel_payback_days:
        text = "مقدار جدید Cancel Payback Days را وارد کنید(برای غیرفعال حذف و بازگشت وجه 0 را وارد کنید):"
        await state.set_state(EditMiscForm.cancel_payback_days)

    elif callback_data.action == MSettingsActions.edit_transaction_logs:
        text = "مقدار جدید Transaction Logs  (برای غیرفعال سازی 0 را وارد کنید) را وارد کنید:"
        await state.set_state(EditMiscForm.transaction_logs)

    elif callback_data.action == MSettingsActions.edit_orders_logs:
        text = (
            "مقدار جدید Orders Logs  (برای غیرفعال سازی 0 را وارد کنید) را وارد کنید:"
        )
        await state.set_state(EditMiscForm.orders_logs)

    elif callback_data.action == MSettingsActions.edit_marzban_webhook_secret:
        text = "مقدار جدید Marzban Webhook secret (برای غیرفعال سازی 0 را وارد کنید) را وارد کنید:"
        await state.set_state(EditMiscForm.marzban_webhook_secret)

    elif callback_data.action == MSettingsActions.edit_force_join_chats:
        text = """
مقدار جدید چت‌های عضویت اجباری را به فورمت زیر را وارد کنید: (هر کدام از چت‌ها در یک خط)
-1001892841234@username1
-1001892845432@username2
برای عدم تنظیم عضویت اجباری 0 را وارد کنید.
        """
        await state.set_state(EditMiscForm.force_join_chats)
    elif callback_data.action == MSettingsActions.edit_remind_invoices_each_n_days:
        text = "مقدار جدید «روز برای یادآوری بدهکاری‌ها» را وارد کنید: (برای غیرفعال سازی یادآوری 0 را وارد کنید)"
        await state.set_state(EditMiscForm.remind_invoices_each_n_days)
    elif callback_data.action == MSettingsActions.edit_remind_invoices_after_amount:
        text = "مقدار جدید «مقدار بدهکاری برای یادآوری» به تومان را وارد کنید:"
        await state.set_state(EditMiscForm.remind_invoices_after_amount)
    else:
        return await query.answer(
            f"Settings not defined for {callback_data.action.value}", show_alert=True
        )
    await query.message.reply(
        text=text,
        reply_markup=cancel_form,
    )


# Misc settings
@router.message(
    StateFilter(EditMiscForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
)
@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.misc),
    IsSuperUser(),
)
async def misc_settings(
    qmsg: CallbackQuery | Message, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    _settings = settings.get_settings()
    text = f"""
پیشوند پروکسی‌ها: <code>{_settings.default_username_prefix}</code>
تعداد سرویس‌های تست روزانه: <code>{_settings.default_daily_test_services}</code>

مدت زمان مجاز شروع از اولین اتصال: {helpers.hr_time(_settings.on_hold_timeout_seconds, lang='fa')}

حذف خودکار اشتراک‌های منقضی شده بعد از: {'هیچوقت' if _settings.delete_expired_users_after_days == 0 else f'{_settings.delete_expired_users_after_days} روز'}

لاگ تراکنش‌ها: <code>{_settings.transaction_logs}</code>
لاگ سفارشات: <code>{_settings.orders_logs}</code>

درصد تخفیف دعوت از دیگران: <code>{_settings.referral_discount_percent}</code>

کارمزد لغو اشتراک: <code>{_settings.cancel_payback_fee}</code>
تعداد روز قبل از امکان لغو اشتراک: <code>{_settings.cancel_payback_days}</code>

Marzban Webhook secret: <code>{_settings.marzban_webhook_secret}</code>

چت‌های عضویت اجباری: <code>{_settings.force_join_chats}</code>

تعداد روز برای یادآوری بدهکاری‌ها: <code>{_settings.remind_invoices_each_n_days}</code>
حداقل مقدار بدهکاری برای یادآوری: <code>{_settings.remind_invoices_after_amount:,}</code>
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text, reply_markup=SettingsMisc(_settings=_settings).as_markup()
        )
    await qmsg.reply(
        text=text, reply_markup=SettingsMisc(_settings=_settings).as_markup()
    )


@router.message(
    EditMiscForm.username_prefix,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_username_prefix(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    username_prefix = message.text.strip()
    if not re.match(r"^(?!_)[A-Za-z0-9_]+$", username_prefix):
        return message.reply(
            "مقدار باید کمتر از ۲۰ کاراکتر و فقط شامل اعداد و حروف بزرگ و کوچک انگلیسی و ـ باشد! دوباره تلاش کنید:"
        )
    origv = _settings.default_username_prefix
    await settings.Settings.update(default_username_prefix=username_prefix)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{username_prefix}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.daily_test_services,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_daily_test_services(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    daily_test_services = message.text.strip()
    try:
        daily_test_services = int(daily_test_services)
    except ValueError:
        return message.reply(
            f"{daily_test_services} مقداری نامعتبر است! مقداری عددی وارد کنید:"
        )
    origv = _settings.default_daily_test_services
    await settings.Settings.update(default_daily_test_services=daily_test_services)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{daily_test_services}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.on_hold_timeout_seconds,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_on_hold_timeout_seconds(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    try:
        if re.match(r"^[0-9]{1,3}(D|d|H|h)$", message.text):
            timeout = 0
            number_pattern = r"^[0-9]{1,3}"
            number = int(re.findall(number_pattern, message.text)[0])
            symbol_pattern = r"(D|d|H|h)$"
            symbol = re.findall(symbol_pattern, message.text)[0].upper()
            if symbol == "H":
                timeout = 3600 * number
            elif symbol == "D":
                timeout += 86400 * number
        else:
            raise ValueError("خطایی در دریافت مدت زمان رخ داد! دوباره تلاش کنید:")
    except ValueError:
        return await message.answer(
            "❌ فرمت ارسالی نامعتبر است! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    origv = _settings.on_hold_timeout_seconds
    await settings.Settings.update(on_hold_timeout_seconds=timeout)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{helpers.hr_time(origv, lang='fa')}</code>
مقدار جدید: <code>{helpers.hr_time(timeout, lang='fa')}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.delete_expired_users_after_days,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_delete_expired_users_after_days(
    message: Message, user: User, state: FSMContext
):
    _settings = settings.get_settings()
    delete_expired_users_after_days = message.text
    try:
        delete_expired_users_after_days = int(delete_expired_users_after_days)
    except ValueError:
        return await message.answer(
            "❌ باید مقداری بیشتر یا مساوی 0 وارد کنید! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    origv = _settings.delete_expired_users_after_days
    await settings.Settings.update(
        delete_expired_users_after_days=delete_expired_users_after_days
    )
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{'هیچوقت' if origv == 0 else f'{origv} روز'}</code>
مقدار جدید: <code>{'هیچوقت' if delete_expired_users_after_days == 0 else f'{delete_expired_users_after_days} روز'}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.transaction_logs,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_transaction_logs(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    transaction_logs = message.text.strip()
    try:
        transaction_logs = int(transaction_logs)
    except ValueError:
        return message.reply(
            f"{transaction_logs} نامعتبر است! لطفا آیدی عددی یک چت تلگرام یا 0 را وارد کنید:"
        )

    if transaction_logs == 0:
        transaction_logs = None
    else:
        try:
            msg = await bot.send_message(
                transaction_logs, text=".", disable_notification=True
            )
        except exceptions.TelegramBadRequest as exc:
            if "chat not found" in str(exc):
                return await message.reply(
                    f"چت <code>{transaction_logs}</code> یافت نشد!"
                )
            if "administrator rights" in str(exc):
                return await message.reply(
                    "ربات باید در گروه/کانال ادمین باشد و دسترسی ارسال پیام داشته باشد!"
                )
            raise exc

        await msg.delete()
    origv = _settings.transaction_logs
    await settings.Settings.update(transaction_logs=transaction_logs)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{transaction_logs}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.orders_logs,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_orders_logs(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    orders_logs = message.text.strip()
    try:
        orders_logs = int(orders_logs)
    except ValueError:
        return message.reply(
            f"{orders_logs} نامعتبر است! لطفا آیدی عددی یک چت تلگرام یا 0 را وارد کنید:"
        )

    if orders_logs == 0:
        orders_logs = None
    else:
        try:
            msg = await bot.send_message(
                orders_logs, text=".", disable_notification=True
            )
        except exceptions.TelegramBadRequest as exc:
            if "chat not found" in str(exc):
                return await message.reply(f"چت <code>{orders_logs}</code> یافت نشد!")
            if "administrator rights" in str(exc):
                return await message.reply(
                    "ربات باید در گروه/کانال ادمین باشد و دسترسی ارسال پیام داشته باشد!"
                )
            raise exc

        await msg.delete()
    origv = _settings.orders_logs
    await settings.Settings.update(orders_logs=orders_logs)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{orders_logs}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.referral_discount_percent,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_referral_discount_percent(
    message: Message, user: User, state: FSMContext
):
    _settings = settings.get_settings()
    referral_discount_percent = message.text.strip()
    try:
        referral_discount_percent = int(referral_discount_percent)
    except ValueError:
        return message.reply(
            f"{referral_discount_percent} نامعتبر است! مقداری عددی وارد کنید:"
        )
    if referral_discount_percent > 100 or referral_discount_percent < 1:
        return message.reply(
            f"{referral_discount_percent} نامعتبر است! مقداری بین 1 تا 100 وارد کنید:"
        )

    origv = _settings.referral_discount_percent
    await settings.Settings.update(referral_discount_percent=referral_discount_percent)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{referral_discount_percent}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.cancel_payback_fee,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_cancel_payback_fee(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    cancel_payback_fee = message.text.strip()
    try:
        cancel_payback_fee = int(cancel_payback_fee)
    except ValueError:
        return message.reply(
            f"{cancel_payback_fee} نامعتبر است! مقداری عددی وارد کنید:"
        )
    if cancel_payback_fee < 0:
        return message.reply(
            f"{cancel_payback_fee} نامعتبر است! مقداری بزرگتر یا مساوی 0 وارد کنید:"
        )
    origv = _settings.cancel_payback_fee
    await settings.Settings.update(cancel_payback_fee=cancel_payback_fee)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{cancel_payback_fee}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.cancel_payback_days,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_cancel_payback_days(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    cancel_payback_days = message.text.strip()
    try:
        cancel_payback_days = int(cancel_payback_days)
    except ValueError:
        return message.reply(
            f"{cancel_payback_days} نامعتبر است! مقداری عددی وارد کنید:"
        )
    if cancel_payback_days < 0:
        return message.reply(
            f"{cancel_payback_days} نامعتبر است! مقداری بزرگتر یا مساوی 0 وارد کنید:"
        )
    origv = _settings.cancel_payback_days
    await settings.Settings.update(cancel_payback_days=cancel_payback_days)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{cancel_payback_days}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.marzban_webhook_secret,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_marzban_webhook_secret(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    marzban_webhook_secret = message.text.strip()
    if marzban_webhook_secret == "0":
        marzban_webhook_secret = None
    origv = _settings.marzban_webhook_secret
    await settings.Settings.update(marzban_webhook_secret=marzban_webhook_secret)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{marzban_webhook_secret}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.force_join_chats,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_force_join_chats(message: Message, user: User, state: FSMContext):
    _settings = settings.get_settings()
    force_join_chats = message.text.strip()
    if force_join_chats == "0":
        fj_chats = None
    else:
        fj_chats = {}
        for chat in force_join_chats.split("\n"):
            try:
                chat_id, username = chat.split("@")
            except ValueError:
                return await message.reply("فرمت نامعتبر! دوباره تلاش کنید:")
            try:
                msg = await bot.send_message(
                    chat_id, text=".", disable_notification=True
                )
                await msg.delete()
            except exceptions.TelegramBadRequest as exc:
                if "chat not found" in str(exc):
                    return await message.reply(
                        f"چت <code>{chat_id}</code> -> @{username} یافت نشد!"
                    )
                if "administrator rights" in str(exc):
                    return await message.reply(
                        "ربات باید در گروه/کانال ادمین باشد و دسترسی ارسال پیام را داشته باشد!"
                    )
                raise exc
            fj_chats.update({chat_id: username})
    origv = _settings.force_join_chats
    await settings.Settings.update(force_join_chats=fj_chats)
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{fj_chats}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.remind_invoices_each_n_days,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_remind_invoices_each_n_days(
    message: Message, user: User, state: FSMContext
):
    _settings = settings.get_settings()
    remind_invoices_each_n_days = message.text.strip()
    try:
        remind_invoices_each_n_days = int(remind_invoices_each_n_days)
    except ValueError:
        return message.reply(
            f"{remind_invoices_each_n_days} نامعتبر است! مقداری عددی وارد کنید:"
        )
    if remind_invoices_each_n_days < 0:
        return message.reply(
            f"{remind_invoices_each_n_days} نامعتبر است! مقداری بزرگتر یا مساوی 0 وارد کنید:"
        )
    origv = _settings.remind_invoices_each_n_days
    await settings.Settings.update(
        remind_invoices_each_n_days=remind_invoices_each_n_days
    )
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{remind_invoices_each_n_days}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


@router.message(
    EditMiscForm.remind_invoices_after_amount,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_remind_invoices_after_amount(
    message: Message, user: User, state: FSMContext
):
    _settings = settings.get_settings()
    remind_invoices_after_amount = message.text.strip()
    try:
        remind_invoices_after_amount = int(remind_invoices_after_amount)
    except ValueError:
        return message.reply(
            f"{remind_invoices_after_amount} نامعتبر است! مقداری عددی وارد کنید:"
        )
    if remind_invoices_after_amount < 100_000:
        return message.reply(
            f"{remind_invoices_after_amount} نامعتبر است! مقداری بزرگتر یا مساوی 100,000 وارد کنید:"
        )
    origv = _settings.remind_invoices_after_amount
    await settings.Settings.update(
        remind_invoices_after_amount=remind_invoices_after_amount
    )
    await state.clear()
    await settings.reload_settings()
    text = f"""
مقدار با موفقیت ویرایش شد!
مقدار قبلی: <code>{origv}</code>
مقدار جدید: <code>{remind_invoices_after_amount}</code>
"""
    await message.reply(text, reply_markup=ReplyKeyboardRemove())
    await misc_settings(message, user)


class EditTextsForm(StatesGroup):
    start = State()
    main_menu = State()
    force_join = State()
    purchase = State()
    support = State()
    help = State()
    command_not_found = State()
    proxy_help = State()
    referral_banner_text = State()
    charge = State()
    verify_phone_number = State()


@router.message(
    StateFilter(EditTextsForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
)
@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.texts),
    IsSuperUser(),
)
async def texts_settings(
    qmsg: CallbackQuery | Message,
    user: User,
    state: FSMContext = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await qmsg.answer(text="Canceled!", reply_markup=ReplyKeyboardRemove())
    text = """
برای مدیریت هر کدام از جواب‌های ربات، دکمه مربوطه را کلیک کنید:
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text, reply_markup=SettingsTexts().as_markup()
        )
    return await qmsg.answer(text=text, reply_markup=SettingsTexts().as_markup())


@router.callback_query(
    SettingsTexts.Callback.filter(),
    IsSuperUser(),
)
async def edit_settings_texts(
    qmsg: CallbackQuery | Message, user: User, callback_data: SettingsTexts.Callback
):
    _texts = texts.get_texts()
    ed_text = None
    if callback_data.field == SettingsTextsActions.start:
        ed_text = _texts.start
    elif callback_data.field == SettingsTextsActions.main_menu:
        ed_text = _texts.main_menu
    elif callback_data.field == SettingsTextsActions.force_join:
        ed_text = _texts.force_join
    elif callback_data.field == SettingsTextsActions.purchase:
        ed_text = _texts.purchase
    elif callback_data.field == SettingsTextsActions.support:
        ed_text = _texts.support
    elif callback_data.field == SettingsTextsActions.help:
        ed_text = _texts.help
    elif callback_data.field == SettingsTextsActions.command_not_found:
        ed_text = _texts.command_not_found
    elif callback_data.field == SettingsTextsActions.proxy_help:
        ed_text = _texts.proxy_help
    elif callback_data.field == SettingsTextsActions.referral_banner_text:
        ed_text = _texts.referral_banner_text
    elif callback_data.field == SettingsTextsActions.charge:
        ed_text = _texts.charge
    elif callback_data.field == SettingsTextsActions.verify_phone_number:
        ed_text = _texts.verify_phone_number
    else:
        text = f"متن برای {callback_data.field.name} تعریف نشده است!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                text=text,
                show_alert=True,
            )
        return await qmsg.answer(text=text)

    text = admin_edit_texts_format(ed_text=ed_text, field=callback_data.field.name)
    markup = SettingsTextsEdit(field=callback_data.field).as_markup()

    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    await qmsg.answer(
        text=text,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


@router.callback_query(
    SettingsTextsEdit.Callback.filter(F.action == "reset"),
    IsSuperUser(),
)
async def texts_reset(
    query: CallbackQuery,
    user: User,
    callback_data: SettingsTextsEdit.Callback,
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "آیا مطمئن هستید که میخواهید این متن را به مقدار پیشفرض بازنشانی کنید؟",
            reply_markup=ConfirmKeyboard(
                data=SettingsTextsEdit.Callback(
                    action="reset", field=callback_data.field, confirmed=True
                ),
                back_to=SettingsTexts.Callback(field=callback_data.field),
            ).as_markup(),
        )
    updates = dict()
    if callback_data.field == SettingsTextsActions.start:
        updates["start"] = texts.StartText()
    elif callback_data.field == SettingsTextsActions.main_menu:
        updates["main_menu"] = texts.MainMenuText()
    elif callback_data.field == SettingsTextsActions.force_join:
        updates["force_join"] = texts.ForceJoinText()
    elif callback_data.field == SettingsTextsActions.purchase:
        updates["purchase"] = texts.PurchaseText()
    elif callback_data.field == SettingsTextsActions.support:
        updates["support"] = texts.SupportText()
    elif callback_data.field == SettingsTextsActions.help:
        updates["help"] = texts.HelpText()
    elif callback_data.field == SettingsTextsActions.command_not_found:
        updates["command_not_found"] = texts.CommandNotFoundText()
    elif callback_data.field == SettingsTextsActions.proxy_help:
        updates["proxy_help"] = texts.ProxyHelpText()
    elif callback_data.field == SettingsTextsActions.referral_banner_text:
        updates["referral_banner_text"] = texts.ReferralBannerText()
    elif callback_data.field == SettingsTextsActions.charge:
        updates["charge"] = texts.ChargeText()
    elif callback_data.field == SettingsTextsActions.verify_phone_number:
        updates["verify_phone_number"] = texts.VerifyPhoneNumber()
    else:
        return await query.answer(
            f"بازنشانی متن برای {callback_data.field.name} تعریف نشده است!"
        )
    await texts.Texts.update(**updates)
    await texts.reload_texts()

    await query.answer(
        f"{callback_data.field.name} به مقدار پیشفرض بازنشانی شد!", show_alert=True
    )
    try:
        await edit_settings_texts(query, user, callback_data)
    except TelegramBadRequest:
        pass


@router.callback_query(
    SettingsTextsEdit.Callback.filter(F.action == "edit"),
    IsSuperUser(),
)
async def texts_edit(
    query: CallbackQuery,
    user: User,
    callback_data: SettingsTextsEdit.Callback,
    state: FSMContext,
):
    if callback_data.field == SettingsTextsActions.start:
        await state.set_state(EditTextsForm.start)
    elif callback_data.field == SettingsTextsActions.main_menu:
        await state.set_state(EditTextsForm.main_menu)
    elif callback_data.field == SettingsTextsActions.force_join:
        await state.set_state(EditTextsForm.force_join)
    elif callback_data.field == SettingsTextsActions.purchase:
        await state.set_state(EditTextsForm.purchase)
    elif callback_data.field == SettingsTextsActions.support:
        await state.set_state(EditTextsForm.support)
    elif callback_data.field == SettingsTextsActions.help:
        await state.set_state(EditTextsForm.help)
    elif callback_data.field == SettingsTextsActions.command_not_found:
        await state.set_state(EditTextsForm.command_not_found)
    elif callback_data.field == SettingsTextsActions.proxy_help:
        await state.set_state(EditTextsForm.proxy_help)
    elif callback_data.field == SettingsTextsActions.referral_banner_text:
        await state.set_state(EditTextsForm.referral_banner_text)
    elif callback_data.field == SettingsTextsActions.charge:
        await state.set_state(EditTextsForm.charge)
    elif callback_data.field == SettingsTextsActions.verify_phone_number:
        await state.set_state(EditTextsForm.verify_phone_number)
    else:
        return await query.answer(
            f"ویرایش متن برای {callback_data.field.name} تعریف نشده است!"
        )
    text = f"""
متن مورد نظر برای قسمت {callback_data.field.name} را ارسال کنید: 
(ربات جهت تست یک بار متن را برای خود شما ارسال ‌می‌کند و اگر موفقیت آمیز بود، متن زخیره می‌شود.)
"""
    await query.message.reply(text=text, reply_markup=cancel_form)


@router.message(
    EditTextsForm.start,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts()
    if not await check_texts(_texts.start, message):
        return
    start = texts.StartText(value=message.text)
    await texts.Texts.update(start=start)
    await texts.reload_texts()
    text = f"""
متن start با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.start),
    )


@router.message(
    EditTextsForm.main_menu,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.main_menu, message):
        return
    main_menu = texts.MainMenuText(value=message.text)
    await texts.Texts.update(main_menu=main_menu)
    await texts.reload_texts()
    text = f"""
متن main_menu با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.main_menu),
    )


@router.message(
    EditTextsForm.force_join,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.force_join, message):
        return
    force_join = texts.ForceJoinText(value=message.text)
    await texts.Texts.update(force_join=force_join)
    await texts.reload_texts()
    text = f"""
متن force_join با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.force_join),
    )


@router.message(
    EditTextsForm.purchase,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.purchase, message):
        return
    purchase = texts.PurchaseText(value=message.text)
    await texts.Texts.update(purchase=purchase)
    await texts.reload_texts()
    text = f"""
متن purchase با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.purchase),
    )


@router.message(
    EditTextsForm.support,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.support, message):
        return
    support = texts.SupportText(value=message.text)
    await texts.Texts.update(support=support)
    await texts.reload_texts()
    text = f"""
متن support با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.support),
    )


@router.message(
    EditTextsForm.help,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.help, message):
        return
    help = texts.HelpText(value=message.text)
    await texts.Texts.update(help=help)
    await texts.reload_texts()
    text = f"""
متن help با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.help),
    )


@router.message(
    EditTextsForm.command_not_found,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.command_not_found, message):
        return
    command_not_found = texts.CommandNotFoundText(value=message.text)
    await texts.Texts.update(command_not_found=command_not_found)
    await texts.reload_texts()
    text = f"""
متن command_not_found با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(
            field=SettingsTextsActions.command_not_found
        ),
    )


@router.message(
    EditTextsForm.proxy_help,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.proxy_help, message):
        return
    proxy_help = texts.StartText(value=message.text)
    await texts.Texts.update(proxy_help=proxy_help)
    await texts.reload_texts()
    text = f"""
متن proxy_help با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.proxy_help),
    )


@router.message(
    EditTextsForm.referral_banner_text,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.referral_banner_text, message):
        return
    referral_banner_text = texts.StartText(value=message.text)
    await texts.Texts.update(referral_banner_text=referral_banner_text)
    await texts.reload_texts()
    text = f"""
متن referral_banner_text با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(
            field=SettingsTextsActions.referral_banner_text
        ),
    )


@router.message(
    EditTextsForm.charge,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.charge, message):
        return
    charge = texts.StartText(value=message.text)
    await texts.Texts.update(charge=charge)
    await texts.reload_texts()
    text = f"""
متن charge با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(field=SettingsTextsActions.charge),
    )


@router.message(
    EditTextsForm.verify_phone_number,
    ~F.text.in_([CancelFormAdmin.cancel]),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
)
async def edit_texts_get(message: Message, user: User, state: FSMContext):  # noqa: F811
    _texts = texts.get_texts()
    if not await check_texts(_texts.verify_phone_number, message):
        return
    verify_phone_number = texts.StartText(value=message.text)
    await texts.Texts.update(verify_phone_number=verify_phone_number)
    await texts.reload_texts()
    text = f"""
متن verify_phone_number با موفقیت ویرایش شد!
==================\n<blockquote>{message.html_text}</blockquote>\n==================
"""
    await message.answer(text)
    await state.clear()
    await edit_settings_texts(
        message,
        user,
        callback_data=SettingsTexts.Callback(
            field=SettingsTextsActions.verify_phone_number
        ),
    )


class EditPayButtonsForm(StatesGroup):
    buttons = State()


# Edit pay buttons
@router.message(
    StateFilter(EditPayButtonsForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
)
@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.pay_buttons),
    IsSuperUser(),
)
async def pay_buttons_settings(
    qmsg: CallbackQuery | Message, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    text = """
شکل قرارگیری دکمه‌های انتخاب مبلغ پرداخت:

مقدار تخفیف‌های نمایش داده شده در ربات تنظیم نشده‌اند و فقط
جهت نمایش است. (به ازای مبالغ بالای 200,000 ده درصد تخفیف اعمال شده است)
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text, reply_markup=PayAmountSetting().as_markup()
        )
    return await qmsg.reply(text=text, reply_markup=PayAmountSetting().as_markup())


@router.callback_query(
    PayAmountSetting.Callback.filter(F.action == PayAmountSettingActions.reset),
    IsSuperUser(),
)
async def reset_pay_buttons_settings(
    query: CallbackQuery,
    user: User,
    callback_data: PayAmountSetting.Callback,
):
    if not callback_data.confirmed:
        text = """
مطمئن هستید که میخواهید تنظیمات دکمه‌های انتخاب مبلغ شارژ به حالت پیشفرض برگردند؟
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmPayAmountSettings(
                action=callback_data.action,
            ).as_markup(),
        )
    await settings.Settings.update(charge_amount_list=None, charge_amount_orders=None)
    await settings.reload_settings()
    text = """
شکل قرارگیری دکمه‌های انتخاب مبلغ پرداخت:
"""
    return await query.message.edit_text(
        text=text, reply_markup=PayAmountSetting().as_markup()
    )


@router.callback_query(
    PayAmountSetting.Callback.filter(F.action == PayAmountSettingActions.edit_amounts),
    IsSuperUser(),
)
async def edit_pay_buttons_settings(
    query: CallbackQuery,
    user: User,
    callback_data: PayAmountSetting.Callback,
    state: FSMContext,
):
    text = """
دکمه‌های مبالغ پرداخت را به ترتیب و جدا شده با / از هم وارد کنید
اگر میخواهید در یک سطر دو دکمه قرار بگیرد آنها را با + از هم جدا کنید.

مثال:
20000 + 30000 / 50000 + 300000 / 500000 + 600000 / 700000 / 800000
"""
    await state.set_state(EditPayButtonsForm.buttons)

    await query.message.reply(
        text,
        reply_markup=CancelFormAdmin().as_markup(
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(
    EditPayButtonsForm.buttons,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_pay_buttons(message: Message, user: User, state: FSMContext):
    rows = [
        [int(col.strip()) for col in row.split("+") if col.strip().isnumeric()]
        for row in message.text.strip().split("/")
        if row
    ]
    orders = [len(row) for row in rows if row]
    if not rows or not orders or (0 in orders):
        return await message.answer("Could not parse input!")

    await settings.Settings.update(
        charge_amount_list=list(chain.from_iterable(rows)), charge_amount_orders=orders
    )
    await state.clear()
    await settings.reload_settings()
    await message.answer("✅ ذخیره شد.", reply_markup=ReplyKeyboardRemove())
    text = """
شکل قرارگیری دکمه‌های انتخاب مبلغ پرداخت:
"""
    return await message.answer(text=text, reply_markup=PayAmountSetting().as_markup())


# --- Topics-group reporting settings (app/utils/reports.py) ------------------


class EditReportsForm(StatesGroup):
    group_id = State()
    backup_interval = State()


@router.message(
    StateFilter(EditReportsForm),
    IsSuperUser(),
    F.text.casefold() == CancelFormAdmin.cancel,
)
@router.callback_query(
    SettingsKeyboard.Callback.filter(F.action == SettingsActions.reports),
    IsSuperUser(),
)
async def reports_settings(
    qmsg: CallbackQuery | Message, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    _settings = settings.get_settings()
    if _settings.reports_group_id:
        text = f"""
🧩 <b>گروه گزارشات (تاپیک‌ها)</b>

گروه متصل: <code>{_settings.reports_group_id}</code>

گزارش‌های ربات در تاپیک‌های این گروه ثبت می‌شوند. با دکمه‌های زیر می‌توانید هر تاپیک را روشن/خاموش کنید:
"""
    else:
        text = """
🧩 <b>گروه گزارشات (تاپیک‌ها)</b>

هنوز گروهی متصل نشده — گزارش‌ها طبق روال قبلی (کانال لاگ تراکنش‌ها/سفارشات) ارسال می‌شوند.

با اتصال یک گروه، ربات تاپیک‌های «مالی، خرید، اکانت تست، بکاپ، شبانه، خطاها، کاربران جدید و سایر» را می‌سازد و همه گزارش‌ها را دسته‌بندی‌شده همان‌جا ثبت می‌کند.
"""
    markup = ReportsSettings(_settings=_settings).as_markup()
    if isinstance(qmsg, CallbackQuery):
        try:
            return await qmsg.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:  # "message is not modified" on toggle spam
            return await qmsg.answer()
    return await qmsg.answer(text, reply_markup=markup)


@router.callback_query(
    ReportsSettings.Callback.filter(F.action == ReportsSettingsActions.set_group),
    IsSuperUser(),
)
async def reports_set_group(
    query: CallbackQuery, user: User, state: FSMContext
):
    await state.set_state(EditReportsForm.group_id)
    await query.message.reply(
        """
آیدی عددی گروه گزارشات را وارد کنید (مثلا <code>-1001234567890</code>).

پیش‌نیازها:
1️⃣ گروه از نوع سوپرگروه باشد و حالت «تاپیک‌ها» (Topics) در تنظیمات گروه روشن باشد.
2️⃣ ربات در گروه <b>ادمین</b> باشد با دسترسی «Manage Topics».

ربات پس از اتصال، تاپیک‌های گزارش را خودش می‌سازد.
""",
        reply_markup=cancel_form,
    )


@router.message(
    EditReportsForm.group_id,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_reports_group_id(message: Message, user: User, state: FSMContext):
    raw = message.text.strip()
    try:
        group_id = int(raw)
    except ValueError:
        return await message.reply(
            f"{raw} نامعتبر است! لطفا آیدی عددی گروه را وارد کنید:"
        )

    wait_msg = await message.reply("♻️ در حال بررسی گروه و ساخت تاپیک‌ها...")
    try:
        mapping = await reports.setup_topics(group_id)
    except reports.ReportSetupError as exc:
        return await wait_msg.edit_text(f"❌ {exc}\n\nدوباره تلاش کنید:")

    await settings.Settings.update(
        reports_group_id=group_id,
        reports_topics=mapping,
        reports_disabled_topics=[],
    )
    await state.clear()
    await settings.reload_settings()

    reports.report(
        reports.ReportTopic.misc,
        "✅ گروه گزارشات با موفقیت به ربات متصل شد!\nاز این پس گزارش‌ها در تاپیک‌های همین گروه ثبت می‌شوند.",
    )
    await wait_msg.edit_text(
        f"✅ گروه <code>{group_id}</code> متصل شد و {len(mapping)} تاپیک ساخته شد!"
    )
    await message.answer("🧩", reply_markup=ReplyKeyboardRemove())
    await reports_settings(message, user)


@router.callback_query(
    ReportsSettings.Callback.filter(F.action == ReportsSettingsActions.unset_group),
    IsSuperUser(),
)
async def reports_unset_group(
    query: CallbackQuery, user: User, callback_data: ReportsSettings.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "گروه گزارشات قطع شود؟ گزارش‌ها به روال قبلی (کانال‌های لاگ) برمی‌گردند.",
            reply_markup=ReportsConfirm().as_markup(),
        )
    await settings.Settings.update(reports_group_id=None, reports_topics={})
    await settings.reload_settings()
    await query.answer("گروه گزارشات قطع شد!", show_alert=True)
    await reports_settings(query, user)


@router.callback_query(
    ReportsSettings.Callback.filter(F.action == ReportsSettingsActions.toggle_topic),
    IsSuperUser(),
)
async def reports_toggle_topic(
    query: CallbackQuery, user: User, callback_data: ReportsSettings.Callback
):
    _settings = settings.get_settings()
    disabled = list(_settings.reports_disabled_topics or [])
    if callback_data.topic in disabled:
        disabled.remove(callback_data.topic)
    else:
        disabled.append(callback_data.topic)
    await settings.Settings.update(reports_disabled_topics=disabled)
    await settings.reload_settings()
    await reports_settings(query, user)


@router.callback_query(
    ReportsSettings.Callback.filter(F.action == ReportsSettingsActions.toggle_nightly),
    IsSuperUser(),
)
async def reports_toggle_nightly(
    query: CallbackQuery, user: User, callback_data: ReportsSettings.Callback
):
    await settings.Settings.update(
        nightly_report_enabled=not settings.get_settings().nightly_report_enabled
    )
    await settings.reload_settings()
    await reports_settings(query, user)


@router.callback_query(
    ReportsSettings.Callback.filter(
        F.action == ReportsSettingsActions.edit_backup_interval
    ),
    IsSuperUser(),
)
async def reports_edit_backup_interval(
    query: CallbackQuery, user: User, state: FSMContext
):
    await state.set_state(EditReportsForm.backup_interval)
    await query.message.reply(
        "بکاپ دیتابیس هر چند ساعت یک‌بار به تاپیک «بکاپ ربات» ارسال شود؟ (1 تا 24 — برای خاموش کردن 0 را وارد کنید)",
        reply_markup=cancel_form,
    )


@router.message(
    EditReportsForm.backup_interval,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_backup_interval(message: Message, user: User, state: FSMContext):
    raw = message.text.strip()
    if not raw.isnumeric() or not (0 <= int(raw) <= 24):
        return await message.reply("عدد بین 0 تا 24 وارد کنید:")
    await settings.Settings.update(backup_interval_hours=int(raw))
    await state.clear()
    await settings.reload_settings()
    await message.reply(
        f"✅ ذخیره شد: {'خاموش' if int(raw) == 0 else f'هر {int(raw)} ساعت'}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await reports_settings(message, user)
