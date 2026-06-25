import sys

from aiogram import F, exceptions
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.handlers.user import account
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction
from app.keyboards.admin.user import ManageUser, ManageUserAction, Users, UsersActions
from app.keyboards.base import CancelUserForm, MainMenu
from app.main import bot
from app.models.audit import AuditLog
from app.models.proxy import Proxy
from app.models.user import ByAdminPayment, Invoice, Transaction, User, UserSetting
from app.utils.audit import record_audit
from app.utils.filters import IsSuperUser
from app.utils.settings import get_settings

from . import generate_commands_help, router


class ManageUserForm(StatesGroup):
    user_id = State()
    amount = State()
    discount_percent = State()
    daily_test_services = State()
    proxy_prefix = State()
    max_postpaid_credit = State()
    custom_name = State()


class SearchUsersForm(StatesGroup):
    user_id = State()
    parent_id = State()
    search_text = State()


@router.message(
    F.text.casefold() == MainMenu.cancel, StateFilter(SearchUsersForm), IsSuperUser()
)
@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.users), IsSuperUser()
)
@router.callback_query(
    Users.Callback.filter(F.action == UsersActions.show), IsSuperUser()
)
async def users(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: AdminPanel.Callback | Users.Callback | None = None,
    search_text: str = None,
):
    if isinstance(callback_data, Users.Callback):
        page = callback_data.current_page
        search_text = callback_data.search_text
    else:
        page = 0
        search_text = None

    q = User.filter().order_by("-custom_name")

    if search_text:
        q = q.filter(
            Q(username__icontains=search_text)
            | Q(custom_name__icontains=search_text)
            | Q(name__icontains=search_text)
        )
    total_count = await q.count()
    q = q.limit(11).offset(0 if page == 0 else page * 10)
    count = await q.count()

    users = await q.all()
    reply_markup = Users(
        users[:10],
        current_page=page,
        count=total_count,
        next_page=True if count > 10 else False,
        prev_page=True if page > 0 else False,
        search_text=search_text,
    ).as_markup()
    start = 1 if page == 0 else (page * 10 + 1)
    end = 10 if page == 0 else ((start - 1) + (10 if count > 10 else count))
    text = f"""
مدیریت و اطلاعات کاربر: <code>/info [user_id|@username]</code>
افزایش موجودی: <code>/charge [user_id|@username] [amount]</code>
کاهش موجودی: <code>/decharge [user_id|@username] [amount]</code>
مسدود کردن: <code>/block [user_id|@username]</code>
رفع مسدودی: <code>/unblock [user_id|@username]</code>

راهنمای کامل دستورات مدیریت کاربران: /usercmd


🔵 لیست کاربران ربات 👇 (برای مدیریت هر کاربر روی آن کلیک کنید)

🚦مشاهده: <b>{start}</b> تا <b>{end}</b> از <b>{total_count}</b>
    """
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=reply_markup,
            )
        return await qmsg.answer(
            text,
            reply_markup=reply_markup,
        )
    except exceptions.TelegramBadRequest:
        pass


@router.callback_query(Users.Callback.filter(F.action == UsersActions.search))
async def search_users_list(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: Users.Callback,
):
    await state.set_state(SearchUsersForm.search_text)
    await query.message.answer(
        "✍️ نام کاربر، یوزرنیم یا نام مستعاری که برای کاربر تنظیم کرده‌اید را برای جستجو وارد کنید:",
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )


@router.message(
    SearchUsersForm.search_text,
    ~CommandStart(),
    ~Command("menu"),
)
async def get_users_serach_text(message: Message, user: User, state: FSMContext):
    text = message.text.replace("\n", " ").strip()
    if len(text) > 64:
        return await message.answer(
            "❌ متن جستجو نمی‌تواند بیشتر از ۶۴ کاراکتر باشد! دوباره وارد کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )
    await state.clear()
    await message.reply("🔎 در حال جستجو...", reply_markup=ReplyKeyboardRemove())
    await users(
        message,
        user,
        callback_data=Users.Callback(
            action=UsersActions.show,
            search_text=text,
        ),
    )


# get user info
@router.message(
    F.text.casefold() == MainMenu.cancel,
    StateFilter(ManageUserForm),
    IsSuperUser(),
)
async def cancel_user_(
    message: Message,
    user: User,
    state: FSMContext,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    await message.reply("عملیات لغو شد!")


@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.info), IsSuperUser()
)
@router.message(Command("info"), IsSuperUser())
@router.message(
    CommandStart(deep_link=True, ignore_case=True, magic=F.args.startswith("info_")),
    IsSuperUser(),
)
async def get_user_info_command(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: ManageUser.Callback | None = None,
    command: CommandObject | None = None,
):
    """Get info of a user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/info @username</code>
        <code>/info 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        current_page = callback_data.current_page
        user_to_get = await User.filter(id=user_id).prefetch_related("setting").first()
    else:
        current_page = 0
        if command.args and command.args.startswith("info_"):
            user_id = command.args.split("info_")[1]
        else:
            try:
                _, user_id = qmsg.text.split()
            except ValueError:
                return await qmsg.answer(
                    "Could not parse the command! format: /info [user_id|username]"
                )
        if user_id.isnumeric():
            user_to_get = (
                await User.filter(id=int(user_id)).prefetch_related("setting").first()
            )
        else:
            user_to_get = (
                await User.filter(username__iexact=user_id.lstrip("@"))
                .prefetch_related("setting")
                .first()
            )

    if not user_to_get:
        return await qmsg.answer(f"User {user_id} not found!")

    proxy_count = await Proxy.filter(user_id=user_to_get.id).count()
    balance = await user_to_get.get_balance()
    credit = await user_to_get.get_available_credit(balance=balance)

    if user_to_get.setting and user_to_get.setting.proxy_username_prefix:
        username_prefix = user_to_get.setting.proxy_username_prefix
    else:
        parent_setting = await UserSetting.filter(user_id=user_to_get.parent_id).first()
        if not parent_setting or not parent_setting.proxy_username_prefix:
            username_prefix = get_settings().default_username_prefix
        else:
            username_prefix = parent_setting.proxy_username_prefix

    text = f"""
شناسه: <code>{user_to_get.id}</code>
نام کاربری: {f'@{user_to_get.username}' if user_to_get.username else '-'}
شماره موبایل: {f'{user_to_get.phone_number}' if user_to_get.phone_number else '-'}


نام: <b>{user_to_get.name}</b>
نام مستعار: {user_to_get.custom_name if user_to_get.custom_name else '-'}

موجودی: <b>{balance:,}</b>
اعتبار در دسترس: <b>{credit:,}</b>

حساب اعتباری؟ / حداکثر اعتبار: {'بله' if user_to_get.is_postpaid else 'خیر'} / {user_to_get.max_post_paid_credit if user_to_get.is_postpaid else 0:,}

مسدود: <b>{'✅' if user_to_get.is_blocked else '❌'}</b>

سطح کاربری: <b>{account.ACCOUNT_TYPE.get(user_to_get.role.name)}</b>
تعداد پروکسی‌ها: <b>{proxy_count}</b>

جمع خرید‌ها: <b>{user_to_get.total_spent:,}</b> تومان

دعوت کننده: <code>{user_to_get.referrer_id if user_to_get.referrer_id else '-'}</code>
تعداد دعوت‌ها: <b>{await user_to_get.referred.all().count()}</b>

<b>تنظیمات:</b>

پیشوند پروکسی‌ها: <code>{username_prefix}</code>
درصد تخفیف: <code>{user_to_get.setting.discount_percentage if user_to_get.setting else 0}%</code>
تعداد سرویس‌های تست روزانه: <code>{user_to_get.setting.daily_test_services if user_to_get.setting else 0}</code>

تأیید خودکار رسید‌های کارت به کارت: {'✅' if user_to_get.card_to_card_auto_accept else '❌'}

دستورات سریع:
    <code>/block {user_to_get.id}</code> <b>مسدود کردن</b>
    <code>/unblock {user_to_get.id}</code> <b>رفع مسدودی</b>
    <code>/charge {user_to_get.id}</code> <i>[amount]</i> <b>افزایش موجودی</b>
    <code>/decharge {user_to_get.id}</code> <i>[amount]</i> <b>کاهش موجودی</b>
    <code>/role {user_to_get.id}</code> <i>[admin|reseller|user]</i> <b>تنظیم سطح کاربری</b>
"""
    markup = ManageUser(user=user_to_get, current_page=current_page).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.cycle_role),
    IsSuperUser(),
)
async def user_cycle_role(
    query: CallbackQuery, user: User, callback_data: ManageUser.Callback
):
    user_to_get = await User.filter(id=callback_data.user_id).first()
    if not user_to_get:
        return await query.answer("کاربر یافت نشد!", show_alert=True)

    if user_to_get.role == User.Role.super_user:
        return await query.answer(
            "امکان تغییر سطح کاربری ادمین اصلی وجود ندارد!", show_alert=True
        )

    try:
        f = iter(User.Role)
        while next(f) != user_to_get.role:
            pass
        user_to_get.role = next(f)
        if user_to_get.role == User.Role.super_user:
            user_to_get.role = next(f)
    except StopIteration:
        user_to_get.role = next(iter(User.Role))  # get first enum value

    await user_to_get.save()
    await query.answer(
        f"سطح کاربری به {account.ACCOUNT_TYPE.get(user_to_get.role.name)} تغییر کرد!",
        show_alert=True,
    )
    await get_user_info_command(
        query,
        user,
        callback_data=ManageUser.Callback(
            user_id=user_to_get.id,
            current_page=callback_data.current_page,
            action=ManageUserAction.info,
        ),
    )


@router.message(Command("role"), IsSuperUser())
async def user_role_command(message: Message, user: User):
    """Change user role

    Args:
        user (int | str): user id or username of the user
        role (str): role of user, [user|reseller|admin|super_user]

    Example:
        <code>/role @username admin</code>
        <code>/role 123456789 admin</code>
    """
    try:
        _, user_id, role = message.text.split()
    except ValueError:
        return await message.answer(
            "Could not parse the command! format: /role [user_id|username] [role]"
        )
    if user_id.isnumeric():
        user_to_get = await User.filter(id=int(user_id)).first()
    else:
        user_to_get = await User.filter(username__iexact=user_id.lstrip("@")).first()

    if not user_to_get:
        return await message.answer(f"User {user_id} not found!")

    roles = {"user": 0, "reseller": 1, "admin": 2, "super_user": 3}
    if role not in roles:
        return await message.answer("Unknown role! must be one of " + "".join(roles))

    user_to_get.role = roles.get(role)
    await user_to_get.save()
    await user_to_get.refresh_from_db()
    text = f"""
Done!

User id: <code>{user_to_get.id}</code>
Role: <code>{user_to_get.role.name}</code>

Actions:

User info: <code>/info {user_id}</code>
"""
    await message.answer(text)


# charge and decharge user
@router.message(Command("charge"), IsSuperUser())
async def charge_user_command(message: Message, user: User):
    """Charge user

    Args:
        user (int | str): user id or username of the user
        amount (int): amount

    Example:
        <code>/charge @username 500000</code>
        <code>/charge 123456789 500000</code>
    """
    try:
        _, user_id, amount = message.text.split()
        amount = int(amount)
    except ValueError:
        return await message.answer(
            "Could not parse the command! format: /charge [user_id|username] [amount]"
        )
    if user_id.isnumeric():
        user_to_get = await User.filter(id=int(user_id)).first()
    else:
        user_to_get = await User.filter(username__iexact=user_id.lstrip("@")).first()

    if not user_to_get:
        return await message.answer(f"User {user_id} not found!")

    async with in_transaction():
        transaction = await Transaction.create(
            type=Transaction.PaymentType.by_admin,
            status=Transaction.Status.finished,
            amount=amount,
            amount_paid=amount,
            user=user_to_get,
        )
        await ByAdminPayment.create(
            by_admin=user,
            transaction=transaction,
        )
    text = f"""
Done!

Transaction id: <code>{transaction.id}</code>
Amount: <code>{transaction.amount:,}</code>
User id: <code>{transaction.user_id}</code>

Actions:

Undo: <code>/undotr {transaction.id}</code>
User info: <code>/info {transaction.user_id}</code>
"""
    await message.answer(text)
    await bot.send_message(
        user_to_get.id,
        f"✅ مبلغ {transaction.amount:,} تومان از طرف <code>{user.id}</code> به حساب شما اضافه شد!",
    )
    await record_audit(
        action="balance.adjust",
        actor=user,
        source=AuditLog.Source.bot,
        target_type="user",
        target_id=user_to_get.id,
        target_label=user_to_get.username or user_to_get.name,
        amount=amount,
        detail={"kind": "charge", "transaction_id": transaction.id},
    )


@router.message(Command("decharge"), IsSuperUser())
async def decharge_user_command(message: Message, user: User):
    """DeCharge user

    Args:
        user (int | str): user id or username of the user
        amount (int): amount

    Example:
        <code>/decharge @username 500000</code>
        <code>/decharge 123456789 500000</code>
    """
    try:
        _, user_id, amount = message.text.split()
        amount = int(amount)
    except ValueError:
        return await message.answer(
            "Could not parse the command! format: /decharge [user_id|username] [amount]"
        )
    if user_id.isnumeric():
        user_to_get = await User.filter(id=int(user_id)).first()
    else:
        user_to_get = await User.filter(username__iexact=user_id.lstrip("@")).first()

    if not user_to_get:
        return await message.answer(f"User {user_id} not found!")

    invoice = await Invoice.create(
        amount=amount,
        type=Invoice.Type.by_admin,
        user=user_to_get,
    )
    text = f"""
Done!

Invoice id: <code>{invoice.id}</code>
Amount: <code>{invoice.amount:,}</code>
User id: <code>{invoice.user_id}</code>

Actions:

Undo: <code>/undoiv {invoice.id}</code>
User info: <code>/info {invoice.user_id}</code>
"""
    await message.answer(text)
    await record_audit(
        action="balance.adjust",
        actor=user,
        source=AuditLog.Source.bot,
        target_type="user",
        target_id=user_to_get.id,
        target_label=user_to_get.username or user_to_get.name,
        amount=-amount,
        detail={"kind": "decharge", "invoice_id": invoice.id},
    )


@router.message(Command("undotr"), IsSuperUser())
async def undotr_command(message: Message, user: User):
    """Remove Transaction

    Args:
        id (int): transaction id

    Example:
        <code>/undotr 112233 </code>
    """
    try:
        _, transaction_id = message.text.split()
        transaction_id = int(transaction_id)
    except ValueError:
        return await message.answer("Could not parse the command! format: /undotr [id]")
    transaction = await Transaction.filter(id=transaction_id).first()

    if not transaction:
        return await message.answer(f"Transaction {transaction_id} not found!")

    await transaction.delete()
    text = f"""
Done!

Transaction id: <code>{transaction.id}</code>
Type: <code>{transaction.type.name}</code>
Amount: <code>{transaction.amount:,}</code>
User id: <code>{transaction.user_id}</code>
"""
    await message.answer(text)
    await record_audit(
        action="balance.adjust",
        actor=user,
        source=AuditLog.Source.bot,
        target_type="user",
        target_id=transaction.user_id,
        amount=-(transaction.amount or 0),
        detail={"kind": "undo_transaction", "transaction_id": transaction_id},
    )


@router.message(Command("undoiv"), IsSuperUser())
async def undoiv_command(message: Message, user: User):
    """Remove Invoice

    Args:
        id (int): invoice id

    Example:
        <code>/undoiv 112233 </code>
    """
    try:
        _, invoice_id = message.text.split()
        invoice_id = int(invoice_id)
    except ValueError:
        return await message.answer("Could not parse the command! format: /undotr [id]")
    invoice = await Invoice.filter(id=invoice_id).first()

    if not invoice:
        return await message.answer(f"invoice {invoice_id} not found!")

    await invoice.delete()
    text = f"""
Done!

Invoice id: <code>{invoice.id}</code>
Type: <code>{invoice.type.name}</code>
Amount: <code>{invoice.amount:,}</code>
User id: <code>{invoice.user_id}</code>
"""
    await message.answer(text)
    await record_audit(
        action="balance.adjust",
        actor=user,
        source=AuditLog.Source.bot,
        target_type="user",
        target_id=invoice.user_id,
        amount=(invoice.amount or 0),
        detail={"kind": "undo_invoice", "invoice_id": invoice_id},
    )


# block and unblock users
@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.block_user), IsSuperUser()
)
@router.message(Command("block"), IsSuperUser())
async def block_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """Block user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/block @username</code>
        <code>/block 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /block [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer(f"User {user_id} not found!")

    if (user_to_get.role == User.Role.super_user) or (user_to_get.id == user.id):
        return await qmsg.answer("You cant do that!")

    if user_to_get.is_blocked:
        return await qmsg.answer("User already blocked")

    user_to_get.is_blocked = True
    await user_to_get.save()
    await qmsg.answer(
        f"User <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> blocked!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.unblock_user), IsSuperUser()
)
@router.message(Command("unblock"), IsSuperUser())
async def unblock_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """Unblock user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/unblock @username</code>
        <code>/unblock 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /unblock [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer(f"User {user_id} not found!")

    if not user_to_get.is_blocked:
        return await qmsg.answer("User is not blocked")

    user_to_get.is_blocked = False
    await user_to_get.save()
    await qmsg.answer(
        f"User <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> unblocked!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


# flip card_to_card_auto_accept
@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.card_to_card_auto_accept),
    IsSuperUser(),
)
async def edit_service_renew(
    query: CallbackQuery, user: User, callback_data: ManageUser.Callback
):
    user_to_get = await User.filter(id=callback_data.user_id).first()
    if not user_to_get:
        return await query.answer("کاربر یافت نشد!", show_alert=True)

    if user_to_get.card_to_card_auto_accept:
        user_to_get.card_to_card_auto_accept = False
        text = """
تأیید خودکار رسید کارت به کارت غیرفعال شد.
❗️❗️با فعال بودن این قابلیت بلافاصله پس از ارسال رسید تراکنش کاربر به صورت خودکار تأیید می‌شود!.
"""
    else:
        user_to_get.card_to_card_auto_accept = True
        text = """
تأیید خودکار رسید کارت به کارت فعال شد.
❗️❗️با فعال بودن این قابلیت بلافاصله پس از ارسال رسید تراکنش کاربر به صورت خودکار تأیید می‌شود!.
"""
    await user_to_get.save()
    await query.answer(text, show_alert=True)
    await get_user_info_command(query, user, callback_data=callback_data)


# make users postpaid or not postpaid
@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.postpaid), IsSuperUser()
)
@router.message(Command("postpaid"), IsSuperUser())
async def postpaid_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """make user postpaid

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/postpaid @username</code>
        <code>/postpaid 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /postpaid [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer("کاربر یافت نشد!")

    if (user_to_get.role == User.Role.super_user) or (user_to_get.id == user.id):
        return await qmsg.answer("شما دسترسی این کار را ندارید!")

    if user_to_get.is_postpaid:
        return await qmsg.answer("کاربر از قبل پس‌پرداخت است!")

    user_to_get.is_postpaid = True
    await user_to_get.save()
    await qmsg.answer(
        f"کاربر <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> به حالت پس پرداخت تبدیل شد!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.nopostpaid), IsSuperUser()
)
@router.message(Command("nopostpaid"), IsSuperUser())
async def nopostpaid_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """make user not postpaid

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/nopostpaid @username</code>
        <code>/nopostpaid 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /nopostpaid [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer("کاربر یافت نشد!")

    if not user_to_get.is_postpaid:
        return await qmsg.answer("کاربر در حالت پس‌پرداخت قرار ندارد!")

    user_to_get.is_postpaid = False
    await user_to_get.save()
    await qmsg.answer(
        f"کاربر <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> از حالت پس‌پرداخت خارج شد!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


# verify/unverify user
@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.verify_user), IsSuperUser()
)
@router.message(Command("verify"), IsSuperUser())
async def verify_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """verify user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/verify @username</code>
        <code>/verify 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /verify [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer("کاربر یافت نشد!")

    if (user_to_get.role == User.Role.super_user) or (user_to_get.id == user.id):
        return await qmsg.answer("شما دسترسی این کار را ندارید!")

    if user_to_get.is_verified:
        return await qmsg.answer("کاربر از قبل تأیید شده است!")

    user_to_get.is_verified = True
    await user_to_get.save()
    await qmsg.answer(
        f"کاربر <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> تأیید شد!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


@router.callback_query(
    ManageUser.Callback.filter(F.action == ManageUserAction.unverify_user),
    IsSuperUser(),
)
@router.message(Command("unverify"), IsSuperUser())
async def unverify_user_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageUser.Callback = None
):
    """un-verify user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/unverify @username</code>
        <code>/unverify 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        user_to_get = await User.filter(id=user_id).first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /unverify [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = await User.filter(id=int(user_id)).first()
        else:
            user_to_get = await User.filter(
                username__iexact=user_id.lstrip("@")
            ).first()

    if not user_to_get:
        return await qmsg.answer("کاربر یافت نشد!")

    if not user_to_get.is_verified:
        return await qmsg.answer("کاربر تأیید نشده است!")

    user_to_get.is_verified = False
    await user_to_get.save()
    await qmsg.answer(
        f"کاربر <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a> از حالت تأیید شده خارج شد!"
    )
    if isinstance(qmsg, CallbackQuery):
        await get_user_info_command(qmsg, user, callback_data=callback_data)


@router.callback_query(
    ManageUser.Callback.filter(),
    IsSuperUser(),
)
async def manage_user_action(
    query: CallbackQuery,
    user: User,
    callback_data: ManageUser.Callback,
    state: FSMContext,
):
    managed_user = await User.filter(
        id=callback_data.user_id,
    ).first()
    if not managed_user:
        return await query.answer("❌ کاربر یافت نشد!")

    if callback_data.action == ManageUserAction.discount_percent:
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

💡 مقدار پیشفرض برای پروکسی‌ها <code>{get_settings().default_username_prefix}</code> می‌باشد

✍️ پیشوند پروکسی را برای تنظیم وارد کنید:
"""
        await state.set_state(ManageUserForm.proxy_prefix)
    elif callback_data.action == ManageUserAction.max_postpaid_credit:
        text = """
💡 برای کاربران اعتباری می‌توانید مقدار اعتبار در دسترس آن‌ها را تعیین کنید
کاربران بدون شارژ حساب می‌توانند تا حداکثر این مقدار از ربات خرید کنند.

توجه کنید که این امکان فقط برای کاربران اعتباری (postpaid) وجود دارد.

💡 مقدار پیشفرض برای کاربران <code>5,000,000</code> تومان می‌باشد

✍️ مقدار اعتبار را برای تنظیم وارد کنید:
"""
        await state.set_state(ManageUserForm.max_postpaid_credit)
    elif callback_data.action == ManageUserAction.custom_name:
        text = """
نام مستعار برای تنظیم برای کاربر مورد نظر را وارد کنید:
(برای حذف نام مستعار 0 را وارد کنید)
"""
        await state.set_state(ManageUserForm.custom_name)
    else:
        return

    await state.set_data(
        {
            "user_id": managed_user.id,
        }
    )
    # await query.message.delete()
    await query.message.answer(
        text,
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )


@router.message(
    ManageUserForm.discount_percent,
    IsSuperUser(),
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

    await state.clear()
    await message.reply(f"درصد تخفیف کاربر به {amount} تنظیم شد!")


@router.message(
    ManageUserForm.daily_test_services,
    IsSuperUser(),
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

    await state.clear()
    await message.reply(f"تعداد سرویس‌های تست روزانه کاربر به {amount} تنظیم شد!")


@router.message(
    ManageUserForm.proxy_prefix,
    IsSuperUser(),
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

    await state.clear()
    await message.reply(
        f"پیشوند پروکسی‌های کاربر به <code>{username_prefix}</code> تنظیم شد!"
    )


@router.message(
    ManageUserForm.max_postpaid_credit,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_max_postpaid_credit(
    message: Message, user: User, state: FSMContext
):
    try:
        amount = int(message.text)
    except ValueError:
        return await message.reply(
            "باید مقداری عددی وارد کنید! لطفا دوباره ارسال کنید:"
        )
    if amount < 1:
        return await message.reply(
            "مقدار باید بیشتر از 0 باشد. در غیر این صورت می‌توانید این قابلیت را برای کاربر غیرفعال کنید! دوباره ارسال کنید:"
        )

    data = await state.get_data()
    await User.filter(id=data.get("user_id")).update(max_post_paid_credit=amount)

    await state.clear()
    await message.reply(f"حداکثر اعتبار در دسترس کاربر به {amount:,} تنظیم شد!")


@router.message(
    ManageUserForm.custom_name,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def manage_users_get_custom_name(message: Message, user: User, state: FSMContext):
    custom_name = message.text.replace("\n", " ").strip()
    if not (3 < len(custom_name) < 64):
        return await message.answer(
            "❌ نام مستعار فقط می‌تواند بین ۴ تا ۶۴ کاراکتر باشد! دوباره ارسال کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )

    data = await state.get_data()

    await User.filter(id=data.get("user_id")).update(custom_name=custom_name)

    await state.clear()
    await message.reply(f"نام مستعار کاربر به <code>{custom_name}</code> تنظیم شد!")


HELP_TEXT = generate_commands_help(sys.modules[__name__])


@router.message(Command("usercmd"), IsSuperUser())
async def show_help_command(message: Message, user: User):
    """Show help message

    /usercmd

    Returns:
        Message: message of help text

    Example:
        /usercmd
    """
    for text in HELP_TEXT:
        await message.reply(text)
