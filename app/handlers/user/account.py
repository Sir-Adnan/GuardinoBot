from datetime import datetime as dt

import pytz
from aiogram import F
from aiogram.filters.command import Command, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)
from tortoise.functions import Sum
from tortoise.transactions import in_transaction

from app.handlers import start
from app.handlers.user import proxy, purchase
from app.keyboards.base import CancelUserForm, MainMenu
from app.keyboards.user.account import (
    ChargeByParent,
    ManageUser,
    ManageUserAction,
    ManageUsers,
    ManageUsersAction,
    RefPanel,
    SharePhoneNumber,
    UserPanel,
    UserPanelAction,
    UserSettings,
    UserSettingsAction,
)
from app.keyboards.user.purchase import Services, ServicesActions
from app.main import bot, get_bot_username
from app.models.service import Discount, Service
from app.models.user import (
    ByAdminPayment,
    GiftPayment,
    Invoice,
    Transaction,
    User,
    UserSetting,
)
from app.utils import settings, texts
from app.utils.filters import AdminAccess, IsJoinedToChannel, PhoneNumberVerified

from . import router

ACCOUNT_TYPE = {
    "user": "کاربر معمولی",
    "reseller": "فروشنده",
    "admin": "ادمین",
    "super_user": "ادمین اصلی",
}


class RedeemCodeForm(StatesGroup):
    code = State()
    service_id = State()
    menu_id = State()
    proxy_id = State()
    user_id = State()
    current_page = State()
    mode = State()


class VerifyPhoneNumber(StatesGroup):
    phone_number = State()


@router.message(
    ~PhoneNumberVerified(),
    ~CommandStart(),
    ~Command("menu"),
    ~StateFilter(VerifyPhoneNumber),
    ~(F.text.in_([MainMenu.cancel, MainMenu.back])),
)
async def check_phone_number_verify(message: Message, user: User, state: FSMContext):
    _texts = texts.get_texts()
    markup = SharePhoneNumber().as_markup(resize_keyboard=True, one_time_keyboard=True)
    await state.set_state(VerifyPhoneNumber.phone_number)
    await message.reply(text=_texts.verify_phone_number.value, reply_markup=markup)


@router.message(
    StateFilter(VerifyPhoneNumber),
    ~CommandStart(),
    ~Command("menu"),
    ~(F.text.in_([MainMenu.cancel, MainMenu.back])),
)
async def get_phone_number_verify(message: Message, user: User, state: FSMContext):
    if (
        message.forward_from
        or not message.contact
        or message.contact.user_id != user.id
    ):
        markup = SharePhoneNumber().as_markup(
            resize_keyboard=True, one_time_keyboard=True
        )
        return await message.reply(
            "🚫 برای ارسال شماره موبایل روی دکمه زیر کلیک کنید👇", reply_markup=markup
        )
    phone_number = message.contact.phone_number.strip().lstrip("+")
    if not phone_number.startswith("98"):
        await message.reply(
            "🚫❗️ تأیید شماره موبایل فقط به وسیله شماره ایران امکان پذیر است😬"
        )
        return await start.main_menu_handler(message, user, state)

    user.phone_number = phone_number
    user.is_verified = True
    await user.save()
    await state.clear()
    await message.reply(
        "✅ شماره موبایل شما با موفقیت تأیید شد و میتونید از ربات استفاده کنید😉"
    )
    return await start.main_menu_handler(message, user, state)


@router.message(F.text.casefold() == MainMenu.back, StateFilter(RedeemCodeForm))
@router.message(F.text == MainMenu.account, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.show))
async def account(qmsg: Message | CallbackQuery, user: User, state: FSMContext):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        # await qmsg.answer("", reply_markup=ReplyKeyboardRemove())
    _settings = settings.get_settings()
    balance = await user.get_balance()
    text = f"""
✅ اطلاعات حساب شما:

💬 نام کاربری: {f'@{user.username}' if user.username else '➖'}
📲 شناسه کاربری: <code>{user.id}</code>
💲 اعتبار در دسترس: <b>{(await user.get_available_credit(balance)):,}</b> تومان
🔋 سرویس‌های فعال: <b>{await user.proxies.all().count()}</b>
"""
    if _settings.referral_system:
        text += f"""~~~~~~~~~~~~~~~~~~~~~~~~
💎 زیرمجموعه‌های من: <b>{await user.referred.all().count()}</b>
"""
    text += f"""~~~~~~~~~~~~~~~~~~~~~~~~
👤 نوع اکانت: {ACCOUNT_TYPE.get(user.role.name)}"""
    if user.is_postpaid:
        text += f""" / پس پرداخت
💳سقف اعتبار شما: {user.max_post_paid_credit:,} تومان
💲بدهکاری: {(balance * -1 if balance < 0 else 0):,} تومان
💸 بستانکاری: {(balance if balance > 0 else 0):,} تومان
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text + "‌‌",
            reply_markup=UserPanel(
                user=user, referral=_settings.referral_system
            ).as_markup(),
        )
    await qmsg.answer(
        text + "‌‌",
        reply_markup=UserPanel(
            user=user, referral=_settings.referral_system
        ).as_markup(),
    )


@router.callback_query(
    UserPanel.Callback.filter(F.action == UserPanelAction.redeem_code),
)
async def redm_code(
    query: CallbackQuery,
    user: User,
    callback_data: UserPanel.Callback,
    state: FSMContext,
):
    await query.message.answer(
        f"💲 کد تخفیف را برای ثبت ارسال کنید:\n🔙 اگه اشتباه وارد این بخش شدید دکمه «{MainMenu.back}» رو بزنید👇",
        reply_markup=CancelUserForm().as_markup(
            resize_keyboard=True, one_time_keyboard=True
        ),
    )
    await state.set_state(RedeemCodeForm.code)
    if callback_data.service_id:
        await state.update_data(
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            proxy_id=callback_data.proxy_id,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
            mode=callback_data.mode,
        )


async def redeem_code(
    discount: Discount, message: Message, user: User, state: FSMContext
) -> None:
    if (discount.expires_at and (discount.expires_at < dt.now(tz=pytz.UTC))) or (
        discount.use_counts and (discount.used_times >= discount.use_counts)
    ):
        text = """😢 متاسفانه این کد تخفیف منقضی شده"""
        await message.answer(text=text)
        return await start.main_menu_handler(message, user, state)

    if discount.once_per_user and await discount.used_by.filter(id=user.id).exists():
        text = """☑️ شما قبلا از این کد تخفیف استفاده کرده‌اید😉"""
        await message.answer(text=text)
        return await start.main_menu_handler(message, user, state)

    if await discount.reserved_by_users.filter(id=user.id).exists():
        text = """☑️ این کد تخفیف از قبل برای شما اعمال شده و میتونید برای خرید ازش استفاده کنید😉"""
        await message.answer(text=text)
        return await start.main_menu_handler(message, user, state)

    await discount.reserved_by_users.add(user)
    data = await state.get_data()
    text = f"""
🎉 تبریک! کد تخفیف {discount.percentage} درصدی برای شما اعمال شد و میتونید برای خرید از اون استفاده کنید😉
"""
    await discount.fetch_related("services")
    if not discount.services:
        q = Service.filter(server__is_enabled=True)
    else:
        q = discount.services.filter(server__is_enabled=True)

    if (mode := data.get("mode")) in ["renew", "reserve"]:
        q = q.filter(renewable=True)
    else:
        q = q.filter(purchaseable=True)

    if user.role == User.Role.user:
        q = q.filter(resellers_only=False)
    elif user.role == User.Role.reseller:
        q = q.filter(users_only=False)
    services = await q.all()
    if services:
        text += """

سرویس‌هایی که این تخفیف روی اون‌ها اعمال میشه:
"""
        svs = [
            (service.id, await service.get_display_name(user=user))
            for service in services
        ]
        await message.answer(
            text, reply_markup=Services(sub_menues=[], services=svs).as_markup()
        )
    else:
        await message.answer(text)

    if service_id := data.get("service_id"):
        if mode == "renew":
            await proxy.renew_proxy_now(
                message,
                user,
                callback_data=proxy.RenewSelectMethod.Callback(
                    proxy_id=data.get("proxy_id"),
                    service_id=data.get("service_id"),
                    menu_id=data.get("menu_id"),
                    user_id=data.get("user_id"),
                    current_page=data.get("current_page"),
                    method=proxy.RenewMethods.now,
                ),
            )
        elif mode == "reserve":
            await proxy.renew_proxy_reserve(
                message,
                user,
                callback_data=proxy.RenewSelectMethod.Callback(
                    proxy_id=data.get("proxy_id"),
                    service_id=data.get("service_id"),
                    menu_id=data.get("menu_id"),
                    user_id=data.get("user_id"),
                    current_page=data.get("current_page"),
                    method=proxy.RenewMethods.reserve,
                ),
            )
        else:
            await purchase.show_service(
                message,
                user,
                callback_data=Services.Callback(
                    service_id=service_id,
                    menu_id=data.get("menu_id", 0),
                    action=ServicesActions.show_service,
                ),
            )
            await state.clear()
    else:
        await start.main_menu_handler(message, user, state)


@router.message(
    RedeemCodeForm.code,
    ~CommandStart(),
    ~Command("menu"),
)
async def redeem_code_user(message: Message, user: User, state: FSMContext):
    discount = await Discount.filter(code=message.text.strip()).first()
    if not discount:
        return await message.answer(
            "❌ کد تخفیف وارد شده نامعتبر است!",
            reply_markup=CancelUserForm().as_markup(
                resize_keyboard=True, one_time_keyboard=True
            ),
        )

    await redeem_code(discount, message, user, state)


@router.message(F.text == MainMenu.referral)
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.referral))
async def referral(qmsg: CallbackQuery | Message, user: User):
    _settings = settings.get_settings()
    if not _settings.referral_system:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                "❌ در حال حاضر بخش زیرمجموعه‌گیری غیرفعال می‌باشد!", show_alert=True
            )
        return await qmsg.answer("❌ در حال حاضر بخش زیرمجموعه‌گیری غیرفعال می‌باشد!")
    referral_count = await user.referred.all().count()
    referral_income = (
        await user.transactions.filter(
            type=Transaction.PaymentType.gift,
        )
        .filter(
            gift_payment__gift_type=GiftPayment.GiftType.referral,
        )
        .all()
        .annotate(sum=Sum("amount"))
        .values_list("amount", flat=True)
    )
    banner = texts.Texts.format(
        texts.get_texts().referral_banner_text,
        INVITE_LINK=f"https://t.me/{get_bot_username()}?start=ref_{user.id}",
    )
    text = f"""
🔥 با دعوت از دیگران میتونید اعتبار هدیه دریافت کنید!

~~~~~~~~~~~~~~~~~~~~~~~~
💎 زیرمجموعه‌های من: <b>{referral_count}</b>
💴 درآمد شما از دعوت دیگران: <b>{(referral_income[0] or 0) if referral_income else 0:,}</b> تومان
~~~~~~~~~~~~~~~~~~~~~~~~
💸 به ازای هر کاربری که از طرف شما وارد ربات میشه، بعد از اولین خریدش {_settings.referral_discount_percent} درصد از مبلغ اون خرید رو به عنوان هدیه دریافت میکنید🤑

💡 مثلا اگه کاربری رو دعوت کردید و ۱۰۰هزارتومن از ربات خرید کرد، {_settings.referral_discount_percent} هزارتومن به عنوان هدیه به اعتبارتون اضافه میشه!

🌵 میتونی با استفاده از لینک زیر دوستات رو به ربات دعوت کنی و اعتبار هدیه بگیری👇👇👇

"""
    if isinstance(qmsg, CallbackQuery):
        await qmsg.message.edit_text(text, reply_markup=RefPanel(user).as_markup())
        await qmsg.message.answer(banner, disable_web_page_preview=True)
    else:
        await qmsg.answer(text)
        await qmsg.answer(banner, disable_web_page_preview=True)


@router.callback_query(
    ManageUsers.Callback.filter(F.action == ManageUsersAction.all),
    AdminAccess(),
)
async def manage_users(
    query: CallbackQuery, user: User, callback_data: ManageUsers.Callback
):
    q = User.filter(parent_id=user.id)
    all_count = await q.count()
    if all_count < 1:
        users = []
        count = 0
    else:
        q = q.limit(11).offset(
            0 if callback_data.current_page == 0 else callback_data.current_page * 10
        )
        users = await q.all()
        count = await q.count()
    text = f"""
🌀 ادمین عزیز به بخش مدیریت کاربران خوش آمدید.

تعداد کاربران تحت مدیریت شما: {all_count}

برای اضافه کردن کاربر میتوانید از آن‌ها بخواهید از طریق لینک زیر وارد ربات شوند:

https://t.me/{get_bot_username()}?start=prnt_{user.id}

لیست کاربران شما:
(برای مدیریت هر کاربر روی آن کلیک کنید)
"""
    await query.message.edit_text(
        text,
        reply_markup=ManageUsers(
            users[:10],
            current_page=callback_data.current_page,
            next_page=True if count > 10 else False,
            prev_page=True if callback_data.current_page > 0 else False,
        ).as_markup(),
    )


class ManageUserForm(StatesGroup):
    user_id = State()
    parent_id = State()
    current_page = State()
    amount = State()
    discount_percent = State()
    daily_test_services = State()
    proxy_prefix = State()


@router.callback_query(
    ManageUsers.Callback.filter(F.action == ManageUsersAction.show_user),
    AdminAccess(),
)
@router.message(F.text == MainMenu.cancel, StateFilter(ManageUserForm), AdminAccess())
async def manage_user(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: ManageUsers.Callback = None,
    state: FSMContext = None,
    cancel_alert: str = "🌀 عملیات لغو شد!",
):
    user_id, current_page = None, None
    if (state is not None) and (await state.get_state() is not None):
        data = await state.get_data()
        user_id, _, current_page = data.values()
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(cancel_alert)
        else:
            await qmsg.answer(text=cancel_alert, reply_markup=ReplyKeyboardRemove())
    if callback_data:
        user_id, current_page = (
            user_id or callback_data.user_id,
            current_page or callback_data.current_page,
        )
    managed_user = (
        await User.filter(id=user_id, parent_id=user.id)
        .prefetch_related("setting")
        .first()
    )
    if not managed_user:
        return await qmsg.answer("❌ کاربر یافت نشد!")
    _settings = settings.get_settings()
    if managed_user.setting and managed_user.setting.proxy_username_prefix:
        username_prefix = managed_user.setting.proxy_username_prefix
    else:
        parent_setting = await UserSetting.filter(
            user_id=managed_user.parent_id
        ).first()
        if not parent_setting or not parent_setting.proxy_username_prefix:
            username_prefix = _settings.default_username_prefix
        else:
            username_prefix = parent_setting.proxy_username_prefix

    balance = await managed_user.get_balance()
    text = f"""
💬 نام کاربری: {f'@{managed_user.username}' if managed_user.username else '➖'}
📲 شناسه کاربری: <code>{managed_user.id}</code>
💲 اعتبار در دسترس: <b>{(await managed_user.get_available_credit(balance)):,}</b> تومان
🔋 سرویس‌های فعال: <b>{await managed_user.proxies.all().count()}</b>
~~~~~~~~~~~~~~~~~~~~~~~~
تعداد سرویس‌های تست روزانه: {managed_user.setting.daily_test_services if managed_user.setting else _settings.default_daily_test_services}
درصد تخفیف: {managed_user.setting.discount_percentage if managed_user.setting else 0}
پیشوند پروکسی‌ها: <code>{username_prefix}</code>
"""
    text += f"""~~~~~~~~~~~~~~~~~~~~~~~~
👤 نوع اکانت: {ACCOUNT_TYPE.get(managed_user.role.name)}"""
    if managed_user.is_postpaid:
        text += f""" / پس پرداخت
💳سقف اعتبار شما: {managed_user.max_post_paid_credit:,} تومان
💲بدهکاری: {(balance * -1 if balance < 0 else 0):,} تومان
💸 بستانکاری: {(balance if balance > 0 else 0):,} تومان
    """
    reply_markup = ManageUser(
        user=managed_user,
        parent_id=user.id,
        current_page=current_page,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=reply_markup)
    await qmsg.answer(
        text,
        reply_markup=reply_markup,
    )


@router.callback_query(
    ManageUser.Callback.filter(),
    AdminAccess(),
)
async def manage_users_action(
    query: CallbackQuery,
    user: User,
    callback_data: ManageUsers.Callback,
    state: FSMContext,
):
    managed_user = await User.filter(
        id=callback_data.user_id, parent_id=user.id
    ).first()
    if not managed_user:
        return await query.answer("❌ کاربر یافت نشد!")

    if callback_data.action == ManageUserAction.charge:
        max_credit = await user.get_available_credit()
        text = f"""
مبلغ مورد نظر برای شارژ حساب کاربر را وارد کنید:
(حداکثر اعتبار موجود شما: {max_credit:,} تومان)
    """
        await state.set_state(ManageUserForm.amount)

    elif callback_data.action == ManageUserAction.discount_percent:
        await user.fetch_related("setting")
        if user.role != User.Role.super_user:
            max_discount = user.setting.discount_percentage if user.setting else 0
            if not max_discount:
                return await query.answer(
                    "درصد تخفیف شما تنظیم نشده است، بنابراین امکان تنظیم برای کاربران خود را ندارید! لطفا با پشتیبانی تماس بگیرید.",
                    show_alert=True,
                )
        else:
            max_discount = 100
        text = f"""
درصد تخفیف جدید کاربر را وارد کنید:
(حداکثر {max_discount} درصد)
    """
        await state.set_state(ManageUserForm.discount_percent)

    elif callback_data.action == ManageUserAction.max_test_services:
        await user.fetch_related("setting")
        if user.role != User.Role.super_user:
            max_count = user.setting.daily_test_services if user.setting else 0
            if not max_count or max_count <= 1:
                return await query.answer(
                    "تعداد سرویس‌های تست شما تنظیم نشده است، بنابراین امکان تنظیم برای کاربران خود را ندارید! لطفا با پشتیبانی تماس بگیرید.",
                    show_alert=True,
                )
        else:
            max_count = "+inf"
        text = f"""
تعداد سرویس‌های تست که این کاربر در یک روز می‌تواند دریافت کند را وارد کنید:
(حداکثر {max_count})
    """
        await state.set_state(ManageUserForm.daily_test_services)

    elif callback_data.action == ManageUserAction.proxy_prefix:
        text = f"""
💡 این متن در ابتدای نام پروکسی‌های شما قرار می‌گیرد و فقط میتواند شامل حروف انگلیسی یا اعداد باشد!

💡 مقدار پیشفرض برای پروکسی‌ها <code>{settings.get_settings().default_username_prefix}</code> می‌باشد

✍️ پیشوند پروکسی را برای تنظیم وارد کنید:
"""
        await state.set_state(ManageUserForm.proxy_prefix)
    else:
        return

    await state.set_data(
        {
            "user_id": managed_user.id,
            "parent_id": user.id,
            "current_page": callback_data.current_page,
        }
    )
    await query.message.delete()
    await query.message.answer(
        text,
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )


@router.message(
    ManageUserForm.amount,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_charge_amount(message: Message, user: User, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply(
            "مبلغ باید مقداری عددی باشد! لطفا دوباره ارسال کنید:"
        )
    user_credit = await user.get_available_credit()
    if amount > user_credit:
        return await message.reply(
            f"مبلغ باید مقداری کمتر از {user_credit:,} باشد! دوباره ارسال کنید:"
        )

    data = await state.get_data()

    text = f"""
شما در حال انتقال مبلغ {amount:,} تومان به کاربر <code>{data.get('user_id')}</code> هستید!

این مبلغ از حساب شما کسر خواهد شد، اگر از انجام این کار مطمئن هستید، دکمه زیر را کلیک کنید:
"""
    await message.reply(
        text,
        reply_markup=ChargeByParent(
            user_id=data.get("user_id"),
            parent_id=data.get("parent_id"),
            amount=amount,
            current_page=data.get("current_page"),
        ).as_markup(),
    )


@router.callback_query(
    ChargeByParent.Callback.filter(),
    AdminAccess(),
)
async def charge_by_parent(
    query: CallbackQuery, user: User, callback_data: ChargeByParent.Callback
):
    managed_user = await User.filter(
        id=callback_data.user_id, parent_id=user.id
    ).first()
    if not managed_user:
        return await query.answer("❌ کاربر یافت نشد!")

    max_credit = await user.get_available_credit()
    if callback_data.amount > max_credit:
        return await query.answer("🚫 اعتبار حساب شما کافی نمی‌باشد!", show_alert=True)

    async with in_transaction():
        invoice = await Invoice.create(
            amount=callback_data.amount,
            type=Invoice.Type.parent_charged_child,
            user=user,
        )
        transaction = await Transaction.create(
            type=Transaction.PaymentType.by_admin,
            status=Transaction.Status.finished,
            finished_at=dt.now(),
            amount=callback_data.amount,
            user=managed_user,
        )
        await ByAdminPayment.create(
            by_admin=user,
            transaction=transaction,
        )
    await query.answer(
        f"✅ عملیات با موفقیت انجام شد و فاکتور به مبلغ {invoice.amount:,} تومان و شماره {invoice.id} برای شما صادر شد!",
        show_alert=True,
    )
    await bot.send_message(
        managed_user.id,
        f"✅ مبلغ {transaction.amount:,} تومان از طرف <code>{user.id}</code> به حساب شما اضافه شد!",
    )
    await manage_users(
        query,
        user,
        callback_data=ManageUsers.Callback(
            user_id=managed_user.id,
            current_page=callback_data.current_page,
            action=ManageUsersAction.show_user,
        ),
    )


@router.message(
    ManageUserForm.discount_percent,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_discount_percent(
    message: Message, user: User, state: FSMContext
):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply(
            "درصد باید مقداری عددی باشد! لطفا دوباره ارسال کنید:"
        )
    if user.role != User.Role.super_user:
        max_discount = user.setting.discount_percentage if user.setting else 0
    else:
        max_discount = 100
    if amount > max_discount:
        return await message.reply(
            f"درصد باید مقداری کمتر از {max_discount} باشد! دوباره ارسال کنید:"
        )

    data = await state.get_data()
    q = UserSetting.filter(user_id=data.get("user_id"))
    if not await q.first():
        await UserSetting.create(
            user_id=data.get("user_id"), discount_percentage=amount
        )
    else:
        await q.update(discount_percentage=amount)

    await manage_user(
        message,
        user,
        state=state,
        cancel_alert=f"درصد تخفیف کاربر به {amount} تنظیم شد!",
    )


@router.message(
    ManageUserForm.daily_test_services,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_daily_test_services(
    message: Message, user: User, state: FSMContext
):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply(
            "تعداد باید مقداری عددی باشد! لطفا دوباره ارسال کنید:"
        )
    if user.role != User.Role.super_user:
        max_count = user.setting.daily_test_services if user.setting else 0
        if amount > max_count:
            return await message.reply(
                f"تعداد باید مقداری کمتر از {max_count} باشد! دوباره ارسال کنید:"
            )

    data = await state.get_data()
    q = UserSetting.filter(user_id=data.get("user_id"))
    if not await q.first():
        await UserSetting.create(
            user_id=data.get("user_id"), daily_test_services=amount
        )
    else:
        await q.update(daily_test_services=amount)

    await manage_user(
        message,
        user,
        state=state,
        cancel_alert=f"تعداد سرویس‌های تست روزانه کاربر به {amount} تنظیم شد!",
    )


@router.message(
    ManageUserForm.proxy_prefix,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_username_prefix(message: Message, user: User, state: FSMContext):
    username_prefix = message.text
    if not username_prefix.isalnum():
        return await message.answer(
            "❌ پیشوند پروکسی‌ها فقط می‌تواند شامل اعداد و حروف انگلیسی باشد! دوباره ارسال کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )
    if not (3 < len(username_prefix) < 20):
        return await message.answer(
            "❌ پیشوند پروکسی‌ها فقط می‌تواند بین ۴ تا ۲۰ کاراکتر باشد! دوباره ارسال کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )

    data = await state.get_data()
    q = UserSetting.filter(user_id=data.get("user_id"))
    if not await q.first():
        await UserSetting.create(
            user_id=data.get("user_id"), proxy_username_prefix=username_prefix
        )
    else:
        await q.update(proxy_username_prefix=username_prefix)

    await manage_user(
        message,
        user,
        state=state,
        cancel_alert=f"پیشوند پروکسی‌های کاربر به <code>{username_prefix}</code> تنظیم شد!",
    )


class SetUsernamePrefixForm(StatesGroup):
    username_prefix = State()


@router.message(
    F.text == MainMenu.cancel,
    SetUsernamePrefixForm.username_prefix,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
@router.callback_query(
    UserPanel.Callback.filter(F.action == UserPanelAction.settings), AdminAccess()
)
async def settings_(
    qmsg: CallbackQuery | Message, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        text = "🌀 عملیات لغو شد!"
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text)
        else:
            await qmsg.answer(text=text, reply_markup=ReplyKeyboardRemove())
    await user.fetch_related("setting")
    text = "⚙️ بخش تنظیمات حساب"
    if not user.setting:
        text += f"""

◀️پیشوند پروکسی‌ها: <code>{settings.get_settings().default_username_prefix}</code>
"""
    else:
        text += f"""

◀️پیشوند پروکسی‌ها: <code>{user.setting.proxy_username_prefix if user.setting.proxy_username_prefix else settings.get_settings().default_username_prefix}</code>
"""
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text + "‌‌", reply_markup=UserSettings(user=user).as_markup()
        )
    return await qmsg.answer(
        text + "‌‌", reply_markup=UserSettings(user=user).as_markup()
    )


@router.callback_query(
    UserSettings.Callback.filter(F.action == UserSettingsAction.username_prefix),
    AdminAccess(),
)
async def username_prefix_set(query: CallbackQuery, user: User, state: FSMContext):
    await state.set_state(SetUsernamePrefixForm.username_prefix)
    text = f"""
💡 این متن در ابتدای نام پروکسی‌های شما قرار می‌گیرد و فقط میتواند شامل حروف انگلیسی یا اعداد باشد!

💡 مقدار پیشفرض برای پروکسی‌ها <code>{settings.get_settings().default_username_prefix}</code> می‌باشد

✍️ پیشوند پروکسی را برای تنظیم وارد کنید:
"""
    await query.message.delete()
    await query.message.answer(
        text,
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_only=True, resize_keyboard=True
        ),
    )


@router.message(
    SetUsernamePrefixForm.username_prefix,
    AdminAccess(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_username_prefix(message: Message, user: User, state: FSMContext):
    username_prefix = message.text
    if not username_prefix.isalnum():
        return await message.answer(
            "❌ پیشوند پروکسی‌ها فقط می‌تواند شامل اعداد و حروف انگلیسی باشد! دوباره ارسال کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )
    if not (3 < len(username_prefix) < 20):
        return await message.answer(
            "❌ پیشوند پروکسی‌ها فقط می‌تواند بین ۴ تا ۲۰ کاراکتر باشد! دوباره ارسال کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )
    await state.clear()
    await user.fetch_related("setting")
    if not user.setting:
        await UserSetting.create(
            user=user,
            proxy_username_prefix=username_prefix,
        )
    else:
        await UserSetting.filter(user_id=user.id).update(
            proxy_username_prefix=username_prefix
        )

    await message.reply(
        f"✅ <code>{username_prefix}</code> به عنوان پیشوند پروکسی‌های شما تنظیم شد."
    )
    await settings(message, user, state=state)
