import asyncio
import math
import random
import uuid
from datetime import datetime as dt
from datetime import timedelta as td
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


PAYMENT_TYPE_FA = {
    Transaction.PaymentType.crypto: "ارز دیجیتال",
    Transaction.PaymentType.card_to_card: "کارت به کارت",
    Transaction.PaymentType.perfectmoney: "پرفکت مانی",
    Transaction.PaymentType.rial_gateway: "درگاه ریالی",
    Transaction.PaymentType.by_admin: "توسط ادمین",
    Transaction.PaymentType.gift: "هدیه",
    Transaction.PaymentType.tronseller: "ترون",
}

TRX_STATUS_FA = {
    Transaction.Status.waiting: "⏳ در انتظار",
    Transaction.Status.failed: "❌ ناموفق",
    Transaction.Status.canceled: "🚫 لغو شده",
    Transaction.Status.partially_paid: "⚠️ پرداخت ناقص",
    Transaction.Status.finished: "✅ تأیید شده",
    Transaction.Status.rejected: "❌ رد شده",
    Transaction.Status.sending: "📤 در حال ارسال",
    Transaction.Status.confirming: "♻️ در حال تأیید",
}


async def payment_method_label(
    transaction: Transaction,
    payment: Union[
        CryptoPayment, CardToCardPayment, PerfectMoneyPayment, ByAdminPayment
    ],
) -> str:
    """Human label for the payment route: type + provider + destination card
    (card-to-card), e.g. 'کارت به کارت (6037...  علی)' / 'ارز دیجیتال (plisio)'."""
    label = PAYMENT_TYPE_FA.get(transaction.type, transaction.type.name)
    provider = getattr(payment, "provider", None)
    if provider is not None:
        label += f" ({getattr(provider, 'value', provider)})"
    if isinstance(payment, CardToCardPayment):
        try:
            await payment.fetch_related("destination_card")
            card = payment.destination_card
        except Exception:  # noqa: BLE001 - label must never break the report
            card = None
        if card:
            label += f"\n💳 کارت مقصد: <code>{card.card_number}</code> ({card.card_holder})"
    return label


async def build_transaction_report(
    transaction: Transaction,
    payment: Union[
        CryptoPayment, CardToCardPayment, PerfectMoneyPayment, ByAdminPayment
    ],
    admin: User | str | None = None,
    note: str | None = None,
) -> str:
    """The financial-report text shared by transaction_log and the explicit
    accept/reject reports (card-to-card / offline)."""
    method = await payment_method_label(transaction, payment)
    admin_line = ""
    if admin is not None:
        if isinstance(admin, User):
            admin_line = (
                f"\n👮 ادمین: <a href='tg://user?id={admin.id}'>"
                f"{admin.name or admin.id}</a>"
            )
        else:
            admin_line = f"\n👮 ادمین: {admin}"
    note_line = f"\n📝 توضیح: {note}" if note else ""
    # gift amount only when present — keeps the report one screen tall
    gift_line = (
        f"\n🎁 هدیه: <code>{transaction.amount_free_given:,}</code> تومان"
        if transaction.amount_free_given
        else ""
    )
    status = TRX_STATUS_FA.get(transaction.status, transaction.status.name)
    return f"""
💳 <b>گزارش تراکنش</b> | {status}

▫️ روش: {method}
💰 مبلغ: <code>{transaction.amount:,}</code> تومان{gift_line}
🧾 فاکتور: <code>{transaction.id}</code>
👤 کاربر: <code>{transaction.user_id}</code>{admin_line}{note_line}
"""


@bg_job
async def transaction_log(
    transaction: Transaction,
    payment: Union[
        CryptoPayment, CardToCardPayment, PerfectMoneyPayment, ByAdminPayment
    ],
    admin: User | str | None = None,
    note: str | None = None,
) -> None:
    # Local import: reports pulls settings lazily; avoids an import cycle here.
    from app.utils import reports

    _settings = settings.get_settings()
    if not _settings.transaction_logs and not reports.group_configured():
        return

    text = await build_transaction_report(transaction, payment, admin=admin, note=note)
    reports.report(
        reports.ReportTopic.financial,
        text,
        legacy_chat_id=_settings.transaction_logs,
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

    from app.utils import reports

    if not _settings.orders_logs and not reports.group_configured():
        return
    await proxy.fetch_related("service")
    is_test = bool(getattr(service, "is_test_service", False)) or not (
        amount_paid or proxy.cost
    )
    title = "🔑 اکانت تست فعال شد:" if is_test else "🛍 سفارش جدید ثبت شد:"
    text = f"""
{title}

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

    reports.report(
        reports.ReportTopic.test_accounts if is_test else reports.ReportTopic.orders,
        text,
        legacy_chat_id=_settings.orders_logs,
    )
