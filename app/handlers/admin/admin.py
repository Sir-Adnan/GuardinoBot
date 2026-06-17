import asyncio
from datetime import UTC, date
from datetime import datetime as dt
from datetime import timedelta as td

from aiogram import F, exceptions
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from jdatetime import datetime as jdt
from tortoise.expressions import Q, Subquery
from tortoise.functions import Count, Sum

from app.keyboards.admin.admin import (
    AdminPanel,
    AdminPanelAction,
    LogPanel,
    LogPanelDuration,
    Stats,
)
from app.keyboards.base import MainMenu
from app.main import bot
from app.models.proxy import Proxy, PurchaseLog
from app.models.service import Service
from app.models.user import Invoice, Transaction, User
from app.utils import helpers
from app.utils.filters import IsSuperUser

from . import logger, router


@router.message(Command("admin"), IsSuperUser())
@router.message(F.text == MainMenu.admin_menu, IsSuperUser())
@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.panel), IsSuperUser()
)
async def show_admin_panel(
    message: Message | CallbackQuery, user: User, state: FSMContext = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()

    text = """
پنل مدیریت ربات:
راهنما: https://t.me/c/2001448048/30
"""
    if isinstance(message, CallbackQuery):
        return await message.message.edit_text(
            text,
            reply_markup=AdminPanel().as_markup(),
        )
    return await message.answer(
        text,
        reply_markup=AdminPanel().as_markup(),
    )


# send message
@router.message(Command("msg"), IsSuperUser())
async def msg_command(message: Message, user: User):
    """send message to a user
    Args:
        user (int | str): user id or username of the user
        text (str): text to be sent to the user

    Example:
        /msg @test hello
    """
    user_id = message.text.split()[1]
    text = " ".join(message.text.split()[2:])

    if user_id.isnumeric():
        user_to_get = await User.filter(id=int(user_id)).first()
    else:
        user_to_get = await User.filter(username__iexact=user_id.lstrip("@")).first()

    if not user_to_get:
        return await message.answer(f"User {user_id} not found!")

    try:
        msg_text = f"""
🔔 شما یک پیام از طرف پشتیبانی دارید:
~~~~~~~~~~~~~~~~~~~~~~~~
{text}
‌‌
"""
        await bot.send_message(chat_id=user_to_get.id, text=msg_text)
        return await message.reply(
            f"message sent to <a href='tg://user?id={user_to_get.id}'>{user_to_get.id}</a>\n\n{msg_text}"
        )
    except Exception as exc:
        await message.reply(f"Error:\n{exc}")
        raise exc


user_blocked_bot_errs = [
    "chat not found",
    "bot can't initiate conversation",
    "bot was blocked by",
]


# Broadcast messages
async def fwd_msg(message: Message, user: User):
    try:
        await message.forward(user.id)
    except exceptions.TelegramRetryAfter as err:
        await asyncio.sleep(err.retry_after)
        return await fwd_msg(message, user)
    except (exceptions.TelegramBadRequest, exceptions.TelegramForbiddenError) as err:
        if any(ext in str(err) for ext in user_blocked_bot_errs):
            user.blocked_bot = True
            await user.save(update_fields=["blocked_bot"])
        logger.error(err)
        return False
    except Exception as err:
        logger.error(f"Unknown error in fwd_msg: {err}")
        return False
    return True


async def send_msg(message: Message, user: User):
    try:
        await bot(message.send_copy(user.id))
    except exceptions.TelegramRetryAfter as err:
        await asyncio.sleep(err.retry_after)
        return await send_msg(message, user)
    except (exceptions.TelegramBadRequest, exceptions.TelegramForbiddenError) as err:
        if any(ext in str(err) for ext in user_blocked_bot_errs):
            user.blocked_bot = True
            await user.save(update_fields=["blocked_bot"])
        logger.error(err)
        return False
    except Exception as err:
        logger.error(f"Unknown error in send_msg: {err}")
        return False
    return True


async def broadcast(
    message: Message, sender: callable, type: str, command: CommandObject
):
    if not message.reply_to_message:
        return await message.reply(f"برای {type} باید روی یک پیام ریپلای کنید!")

    success = 0
    fails = 0
    waiter = 0.1
    users_q = User.filter(is_blocked=False, blocked_bot=False)

    args = (
        {c.split("=")[0]: c.split("=")[1] for c in command.args.split()}
        if command.args
        else {}
    )
    text = ""
    if (server_id := args.get("svid", None)) is not None:
        users_q = users_q.filter(proxies__server_id=server_id)
        text += f"درحال {type} به کاربران سرور با شناسه {server_id}\n"
    if (service_id := args.get("srid", None)) is not None:
        users_q = users_q.filter(proxies__service_id=service_id)
        text += f"درحال {type} به کاربران سرویس با شناسه {service_id}\n"

    users_q = users_q.distinct()
    users = await users_q.all()
    total = len(users)

    text += f"\n{type} پیام به {total} کاربر..."
    progres = await message.reply(
        text=f"{text}\nپیشرفت: {0}%\nزمان تقریبی: {int((waiter*total)/60)} دقیقه"
    )

    for idx, user in enumerate(users):
        if await sender(message.reply_to_message, user):
            success += 1
        else:
            fails += 1
        if idx and (idx % 250) == 0:
            await progres.edit_text(
                f"{text}\nپیشرفت: {int(idx/total*100)}%\nزمان تقریبی: {int((waiter*(total-idx))/60)} دقیقه"
            )
        await asyncio.sleep(0.1)
    await progres.edit_text(f"{text} \nپیشرفت: 100%")
    return await message.reply(f"پیام {type} شد!\nموفق: {success}\n ناموفق: {fails}")


@router.message(Command("forward"), IsSuperUser())
async def forward_command(message: Message, user: User, command: CommandObject):
    """forwards a message to all users

    Example:
        /forward (reply)
    """
    asyncio.create_task(broadcast(message, fwd_msg, "فوروارد", command=command))


@router.message(Command("broadcast"), IsSuperUser())
async def broadcast_command(message: Message, user: User, command: CommandObject):
    """sends a message to all users

    Example:
        /broadcast (reply)
    """
    asyncio.create_task(broadcast(message, send_msg, "ارسال", command=command))


@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.stats), IsSuperUser()
)
async def show_stats(
    query: CallbackQuery | Message, user: User, state: FSMContext | None = None
):
    users_count = await User.all().count()
    users_today = await User.filter(created_at__gt=dt.now() - td(days=1)).all().count()
    users_month = await User.filter(created_at__gt=dt.now() - td(days=30)).all().count()
    blocked_users = await User.filter(is_blocked=True).all().count()

    proxies_count = await Proxy.all().count()
    proxies_today = (
        await Proxy.filter(created_at__gt=dt.now() - td(days=1)).all().count()
    )
    proxies_month = (
        await Proxy.filter(created_at__gt=dt.now() - td(days=30)).all().count()
    )

    most_used_services = (
        await Service.annotate(num_prx=Count("proxies"))
        .filter(
            num_prx__gt=0,
        )
        .group_by("id")
        .order_by("-num_prx")
        .values_list("name", "num_prx")
    )
    msv = "\n".join(
        [
            f"<i>{i}</i> - <code>{sr[0]}:</code> <b>{sr[1]}</b>"
            for i, sr in enumerate(most_used_services, 1)
        ]
    )
    text = f"""
<b>آمار کاربران ربات:</b>

کل کاربران: <code>{users_count}</code>
کاربران عضو شده در ۲۴ ساعت گذشته: <code>{users_today}</code>
کاربران عضو شده در ۳۰ روز گذشته: <code>{users_month}</code>
کاربران مسدود شده: <code>{blocked_users}</code>


<b>آمار پروکسی‌ها:</b>

کل پروکسی‌ها: <code>{proxies_count}</code>
پروکسی‌های ساخته شده در ۲۴ ساعت گذشته: <code>{proxies_today}</code>
پروکسی‌های ساخته شده در ۳۰ روز گذشته: <code>{proxies_month}</code>

پر استفاده ترین سرویس‌ها:
{msv}


آمار فروش ۳۰ روز گذشته:
{await get_purchase_logs(start_date=dt.now(UTC).date() - td(days=30), end_date=dt.now(UTC).date())}

💡 <i>برای دریافت آمار فروش دستور /plog را ارسال کنید</i>
"""
    return await query.message.edit_text(text, reply_markup=Stats().as_markup())


DATE_FMT = "%Y-%m-%d %H:%M"


async def get_purchase_logs(start_date: dt | date, end_date: dt | date) -> str:
    if isinstance(start_date, date):
        start_date = dt(
            year=start_date.year,
            month=start_date.month,
            day=start_date.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    if isinstance(end_date, date):
        end_date = dt(
            year=end_date.year,
            month=end_date.month,
            day=end_date.day,
            hour=23,
            minute=59,
            second=59,
            microsecond=999,
        )

    q = PurchaseLog.filter(created_at__gt=start_date, created_at__lt=end_date)

    total_count = await q.count()
    total_cost = (
        await q.annotate(sum=Sum("amount")).all().values_list("sum", flat=True)
    )[0] or 0

    # all purchases with data_limit
    total_gb_q = q.filter(Q(data__isnull=False), ~Q(data=0)).all()
    total_gb_count = await total_gb_q.count()
    if total_gb_count:
        total_gb = (
            await total_gb_q.annotate(sum=Sum("data")).values_list("sum", flat=True)
        )[0]
        total_gb_cost = (
            await total_gb_q.annotate(sum=Sum("amount")).values_list("sum", flat=True)
        )[0]
    else:
        total_gb = 0
        total_gb_cost = 0

    # all purchases without data_limit
    total_inf_q = q.filter(Q(data__isnull=True) | Q(data=0)).all()
    total_inf_count = await total_inf_q.count()
    if total_inf_count:
        total_inf_cost = (
            await total_inf_q.annotate(sum=Sum("amount")).values_list("sum", flat=True)
        )[0]
    else:
        total_inf_cost = 0

    # transactions logs
    transactions = (
        await Transaction.filter(
            created_at__gt=start_date,
            created_at__lt=end_date,
        )
        .filter(
            ~Q(type=Transaction.PaymentType.gift),
            status__in=[
                Transaction.Status.finished,
                Transaction.Status.partially_paid,
            ],
        )
        .all()
        .annotate(total_amount=Sum("amount_paid"))
        .group_by("type")
        .order_by("total_amount")
        .values_list("type", "total_amount")
    )

    tr_text = ""
    tr_total = 0
    for tr in transactions:
        _type, amount = tr
        if amount:
            tr_total += amount
            tr_text += f"<b>{_type.name}</b>: <code>{amount:,}</code> تومان\n"

    user_balances_q = (  # query to fetch sum of transactions and invoices amount of all users
        await Transaction.filter(status=Transaction.Status.finished)
        .annotate(trx_sum=Sum("amount"))
        .annotate(
            inv_sum=Subquery(
                Invoice.filter(is_draft=False)
                .annotate(inv=Sum("amount"))
                .all()
                .values_list("inv", flat=True)
            )
        )
        .all()
        .values("trx_sum", "inv_sum")
    )[0]

    user_balances_total = int(user_balances_q.get("trx_sum") or 0) - int(
        user_balances_q.get("inv_sum") or 0
    )

    text = f"""
خلاصه گزارش فروش:
تاریخ شروع: <code>{start_date.strftime(DATE_FMT)}</code>
تاریخ پایان: <code>{end_date.strftime(DATE_FMT)}</code>

تعداد کل فروش: <code>{total_count:,}</code>
جمع کل فروش: <code>{total_cost:,}</code> تومان

فروش حجمی:
تعداد کل فروش: <code>{total_gb_count:,}</code>
جمع کل فروش: <code>{total_gb_cost:,}</code> تومان
جمع گیگ فروخته شده: <code>{helpers.hr_size(total_gb, lang='fa')}</code>

فروش نامحدود:
تعداد کل فروش: <code>{total_inf_count:,}</code>
جمع کل فروش: <code>{total_inf_cost:,}</code> تومان

💡 <b>تمام آمارها شامل خرید، تمدید و رزروها می‌باشد</b>


گزارش تراکنش‌هابه تفکیک متود پرداخت:
{tr_text}
جمع کل: <code>{tr_total:,}</code>


بدون در نظر گرفتن بازه زمانی:

جمع کل موجودی در دسترس کاربران: <code>{user_balances_total:,}</code> 
(منفی بودن به معنی بدهکاری است)
"""
    return text


INPUT_DATE_FMT = "%d-%m-%Y"


@router.message(Command("plog"), IsSuperUser())
async def show_logs(message: Message, user: User, command: CommandObject):
    if not command.args:
        text = await get_purchase_logs(
            start_date=dt.now(UTC).date() - td(days=30), end_date=dt.now(UTC).date()
        )
    elif len(command.args.strip().split()) == 1:
        try:
            start_date = dt.strptime(command.args.strip(), INPUT_DATE_FMT)
            text = await get_purchase_logs(start_date=start_date, end_date=dt.now(UTC))
        except ValueError as err:
            text = f"فرمت ارسال دستور اشتباه است!\n\n<code>{err}</code>\n\n"
    elif len(command.args.strip().split()) == 2:
        try:
            start, end = command.args.strip().split()
            start_date = dt.strptime(start.strip(), INPUT_DATE_FMT)
            end_date = dt.strptime(end.strip(), INPUT_DATE_FMT)
            text = await get_purchase_logs(start_date=start_date, end_date=end_date)
        except ValueError as err:
            text = f"فرمت ارسال دستور اشتباه است!\n\n<code>{err}</code>\n\n"

    else:
        text = "فرمت ارسال دستور اشتباه است!\n\n"

    text += """
فرمت دستور:
<code>/plog <b>[start]</b> <b>[end]</b></code>

فرمت تاریخ‌ها: <b>day-month-year</b>: <code>25-9-2023</code>
مثلا:
<code>/plog 12-5-2023 15-5-2023</code>
از تاریخ 12-5-2023 تا تاریخ 15-5-2023
یا
<code>/plog 12-5-2023</code>
از تاریخ 15-5-2023 تا زمان حال
"""
    await message.reply(text=text, reply_markup=LogPanel().as_markup())


@router.callback_query(LogPanel.Callback.filter(), IsSuperUser())
async def show_logs_cq(
    query: CallbackQuery, user: User, callback_data: LogPanel.Callback
):
    if callback_data.duration == LogPanelDuration.today:
        text = await get_purchase_logs(
            start_date=dt.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0),
            end_date=dt.now(UTC),
        )
    elif callback_data.duration == LogPanelDuration.this_week:
        text = await get_purchase_logs(
            start_date=(dt.now(UTC) - td(days=jdt.utcnow().weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            end_date=dt.now(UTC),
        )
    elif callback_data.duration == LogPanelDuration.last_24_h:
        text = await get_purchase_logs(
            start_date=dt.now(UTC) - td(hours=24),
            end_date=dt.now(UTC),
        )
    elif callback_data.duration == LogPanelDuration.last_7_d:
        text = await get_purchase_logs(
            start_date=dt.now(UTC) - td(days=7),
            end_date=dt.now(UTC),
        )
    elif callback_data.duration == LogPanelDuration.last_30_d:
        text = await get_purchase_logs(
            start_date=dt.now(UTC) - td(days=30),
            end_date=dt.now(UTC),
        )
    else:  # callback_data.duration == LogPanelDuration.this_month:
        text = await get_purchase_logs(
            start_date=dt.now(UTC).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ),
            end_date=dt.now(UTC),
        )
    await query.answer("♻️ در حال بروزرسانی داده‌ها...")
    try:
        await query.message.edit_text(text=text, reply_markup=LogPanel().as_markup())
    except exceptions.TelegramBadRequest as err:
        if "message is not modified" in str(err):
            return
        raise err
