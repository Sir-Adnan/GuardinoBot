import asyncio
import json
import math
import random
import uuid
from datetime import datetime as dt
from datetime import timedelta as td
from html import escape
from typing import Any, Awaitable, Callable, Literal, Union

from aiogram import exceptions
from jdatetime import datetime as jdt
from pytz import timezone
from tortoise.transactions import in_transaction

from app.logger import get_logger
from app.main import bot, get_bot_username, scheduler
from app.models.proxy import Proxy, PurchaseLog, Reserve
from app.models.server import Server
from app.models.service import Service
from app.models.user import (
    ByAdminPayment,
    CardToCardPayment,
    CryptoPayment,
    PerfectMoneyPayment,
    Transaction,
    User,
)

# from app.utils.settings import Settings, UsernameGenerators
from app.utils import settings

from .bg import bg_job

# from app.utils.settings import Settings, get_settings


logger = get_logger("utils/helpers")

intervals_en = (
    ("months", 2592000),  # 60 * 60 * 24 * 30
    ("days", 86400),  # 60 * 60 * 24
    ("hours", 3600),  # 60 * 60
    ("minutes", 60),
    ("seconds", 1),
)


intervals_fa = (
    ("ماه", 2592000),  # 60 * 60 * 24 * 30
    ("روز", 86400),  # 60 * 60 * 24
    ("ساعت", 3600),  # 60 * 60
    ("دقیقه", 60),
    ("ثانیه", 1),
)


def hr_time(seconds: int, lang: Literal["en", "fa"] = "fa", granularity: int = 2):
    """turns seconds into human readable time"""
    if seconds < 0:
        seconds = 0
    result = []

    intervals = intervals_fa if lang == "fa" else intervals_en
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1 and lang == "en":
                name = name.rstrip("s")
            result.append(f"{int(value)} {name}")
    return " و ".join(result[:granularity])


def hr_date(timestamp: int, format: str = "%Y/%m/%d %H:%M") -> str:
    return jdt.fromtimestamp(timestamp, tz=timezone("Asia/Tehran")).strftime(format)


def get_until_expires(expire_timestamp: int, lang: Literal["en", "fa"] = "fa") -> str:
    return hr_time(expire_timestamp - dt.now().timestamp(), lang=lang)


size_names_en = (
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
    "PB",
    "EB",
    "ZB",
    "YB",
)
size_names_fa = (
    "بایت",
    "کیلوبایت",
    "مگابایت",
    "گیگابایت",
    "ترابایت",
    "پتابایت",
    "اگزابایت",
    "زتابایت",
    "یوتابایت",
)


def hr_size(size_bytes: int, lang: Literal["en", "fa"] = "fa"):
    size_names = size_names_fa if lang == "fa" else size_names_en
    if size_bytes <= 0:
        return "0"
    size_index = int(math.floor(math.log(size_bytes, 1024)))
    size = round(size_bytes / math.pow(1024, size_index), 2)
    return f"{size:g} {size_names[size_index]}"


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(value) -> str:
    """Latin digits → Persian digits (display only)."""
    return str(value).translate(_FA_DIGITS)


def usage_bar(used: int, limit: int, width: int = 10, lang: str = "fa") -> str:
    """Text data-usage bar, e.g. ``▰▰▰▱▱▱▱▱▱▱ ۳۲٪``. Returns '' for unlimited
    plans (no limit) so callers can simply append it."""
    if not limit or limit <= 0:
        return ""
    pct = max(0, min(100, int(round((used or 0) / limit * 100))))
    filled = int(round(pct / 100 * width))
    bar = "▰" * filled + "▱" * (width - filled)
    pct_s = fa_num(pct) if lang == "fa" else str(pct)
    return f"{bar} {pct_s}٪"


async def check_username_exists(username: str) -> bool:
    return await User.filter(username=username).exists()


def generate_random_text(min_length: int = 4, max_length: int = 8) -> str:
    return (str(uuid.uuid4())[: random.randint(min_length, max_length)]).replace(
        "-", ""
    )


async def generate_randomized_username(username: str) -> str:
    _username = username + generate_random_text()

    if _username.endswith("_"):
        return _username[:-1]

    if await check_username_exists(_username):
        return await generate_randomized_username(username=username)
    return _username


async def generate_incremental_username(
    username: str,
    server_id: int,
    padding: int = 4,
    increment_by: int = 1,
    last_id: int = None,
) -> str:
    if not last_id:
        last_id = (
            await Server.filter(id=server_id)
            .first()
            .values_list("total_proxies", flat=True)
        )

    _username = username + str(last_id + increment_by).rjust(padding, "0")

    if await check_username_exists(_username):
        return await generate_incremental_username(
            username=username,
            server_id=server_id,
            padding=padding,
            increment_by=increment_by + 1,
            last_id=last_id,
        )
    return _username


async def generate_proxy_username(
    user: User,
    server_id: int,
    _settings: "settings.Settings",
    max_length: int = 32,
) -> str:
    if user.setting and user.setting.proxy_username_prefix:
        username = user.setting.proxy_username_prefix
    elif user.parent_id:
        await user.fetch_related("parent", "parent__setting")
        if user.parent.setting and user.parent.setting.proxy_username_prefix:
            username = user.parent.setting.proxy_username_prefix
        else:
            username = _settings.default_username_prefix
    else:
        username = _settings.default_username_prefix
    if not username.endswith("_"):
        username += "_"
    if _settings.username_generator == settings.UsernameGenerators.incremental:
        return await generate_incremental_username(
            username=username, server_id=server_id
        )
    else:
        return await generate_randomized_username(username=username)


def get_expire_timestamp(expire_duration: int) -> int:
    return int((dt.today() + td(seconds=expire_duration)).timestamp())


async def check_force_join(user: User, force_join_chats: dict[str, str]) -> bool:
    for channel_id in force_join_chats:
        try:
            if (await bot.get_chat_member(channel_id, user.id)).status == "left":
                return False
        except Exception as err:
            logger.error(f"Error checking force_join: {err}")

    user.force_join_check = dt.now()
    await user.save()
    return True


def reserve_job_queued(proxy_id: int) -> bool:
    if scheduler.get_job(f"reserves:queue:{proxy_id}"):
        return True
    return False


async def log_sender(
    func: Callable[[Any, Any], Awaitable[Any]],
    *args,
    **kwargs,
) -> None:
    for _ in range(3):
        try:
            return await func(*args, **kwargs)
        except exceptions.TelegramBadRequest:
            pass
        except exceptions.TelegramRetryAfter as err:
            await asyncio.sleep(err.retry_after)


@bg_job
async def transaction_log(
    transaction: Transaction,
    payment: Union[
        CryptoPayment, CardToCardPayment, PerfectMoneyPayment, ByAdminPayment
    ],
) -> None:
    _settings = settings.get_settings()
    if not _settings.transaction_logs:
        return

    text = f"""
تراکنش جدید!

نوع: {transaction.type.name}
وضعیت: <b>{transaction.status.name}</b>

مبلغ: <code>{transaction.amount:,}</code>
مبلغ هدیه: <code>{transaction.amount_free_given:,}</code>

کاربر: <a href='tg://user?id={transaction.user_id}'>{transaction.user_id}</a>

برای دریافت اطلاعات کاربر روی لینک زیر کلیک کنید:
https://t.me/{get_bot_username()}?start=info_{transaction.user_id}

دیتای تراکنش:
<code>{escape(json.dumps(dict(payment), indent=2, default=str))}</code>
"""
    await log_sender(
        bot.send_message,
        chat_id=_settings.transaction_logs,
        text=text,
        disable_web_page_preview=True,
    )


transalte_order_type = {"new": "خرید", "renew": "تمدید", "reserve": "رزرو پشتیبان"}


@bg_job
async def order_log(
    proxy: Proxy,
    type: Literal["new", "renew", "reserve"],
    service: Service,
    user: User,
    amount_paid: float,
    reserve: Reserve = None,
) -> None:
    _settings = settings.get_settings()
    async with in_transaction():
        if type == "reserve" and not reserve:
            raise ValueError("type is set to 'reserve' but reserve is not provided!")
        if type == "new":
            await PurchaseLog.create(
                type=PurchaseLog.Type.purchase,
                amount=amount_paid,
                data=service.data_limit,
                proxy=proxy,
                service=service,
                user=user,
            )
        elif type == "renew":
            await PurchaseLog.create(
                type=PurchaseLog.Type.renew,
                amount=amount_paid,
                data=service.data_limit,
                proxy=proxy,
                service=service,
                user=user,
            )
        elif type == "reserve":
            await PurchaseLog.create(
                type=PurchaseLog.Type.reserve,
                amount=amount_paid,
                data=service.data_limit,
                reserve=reserve,
                proxy=proxy,
                service=service,
                user=user,
            )

    if not _settings.orders_logs:
        return
    await proxy.fetch_related("service")
    text = f"""
سفارش جدید ثبت شد:

نوع: <b>{transalte_order_type.get(type.lower(), type.capitalize())}</b>

شماره اشتراک: <code>{proxy.id}</code>
نام اشتراک: <code>{proxy.username}</code>
هزینه: <code>{proxy.cost if proxy.cost else 0:,}</code>
سرویس: <b>{proxy.service.display_name}</b>

مبلغ پرداختی: <code>{amount_paid:,}</code>

User: <a href='tg://user?id={proxy.user_id}'>{proxy.user_id}</a>

برای دریافت اطلاعات کاربر روی لینک زیر کلیک کنید:
https://t.me/{get_bot_username()}?start=info_{proxy.user_id}
"""

    await log_sender(
        bot.send_message,
        chat_id=_settings.orders_logs,
        text=text,
        disable_web_page_preview=True,
    )
