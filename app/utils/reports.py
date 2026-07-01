"""Topics-group reporting: route admin reports into a Telegram forum supergroup,
one topic per category (like the competitor bots' "reports group").

Behavior contract (backward compatible):
  * No reports group configured -> every call falls back to its LEGACY
    destination (``legacy_chat_id`` e.g. transaction_logs/orders_logs, or the
    super-users' PV) — existing deployments behave exactly as before.
  * Group configured -> reports go ONLY to the group topics (the group
    replaces the legacy channels, per owner's decision). A per-topic disable
    switch drops that category silently.
  * A topic deleted by an admin is re-created once on demand; if that fails the
    message lands in the group's General so nothing is lost.

All sends are fire-and-forget (@bg_job) and flood-aware (min gap between group
sends + retry on Telegram RetryAfter). This module must never raise into its
callers and must never report its own failures to the errors topic (anti-loop);
they only go to the logger.
"""

import asyncio
import time
from enum import Enum
from typing import Optional

from aiogram import exceptions
from aiogram.types import BufferedInputFile

import config
from app.logger import get_logger
from app.main import bot
from app.utils.bg import bg_job

logger = get_logger("utils/reports")


class ReportTopic(str, Enum):
    financial = "financial"  # receipt accepted/rejected, gateway credits
    orders = "orders"  # purchases / renews / reserves
    test_accounts = "test_accounts"  # test-service activations
    backup = "backup"  # periodic DB dumps
    nightly = "nightly"  # end-of-day summary
    errors = "errors"  # unhandled bot/web-panel errors (sanitized)
    new_users = "new_users"  # first /start of a user
    misc = "misc"  # hub-balance alerts, payment mismatches, ...


# Topic title + icon color used on creation (Bot API allowed icon_color values).
TOPIC_TITLES: dict[ReportTopic, str] = {
    ReportTopic.financial: "💰 گزارش مالی",
    ReportTopic.orders: "🛍 گزارش خرید و تمدید",
    ReportTopic.test_accounts: "🔑 اکانت تست",
    ReportTopic.backup: "🤖 بکاپ ربات",
    ReportTopic.nightly: "🌙 گزارش شبانه",
    ReportTopic.errors: "❌ گزارش خطاها",
    ReportTopic.new_users: "🎉 کاربران جدید",
    ReportTopic.misc: "⚙️ سایر گزارشات",
}
TOPIC_COLORS: dict[ReportTopic, int] = {
    ReportTopic.financial: 9367192,  # green
    ReportTopic.orders: 7322096,  # blue
    ReportTopic.test_accounts: 16766590,  # yellow
    ReportTopic.backup: 13338331,  # violet
    ReportTopic.nightly: 7322096,  # blue
    ReportTopic.errors: 16478047,  # red
    ReportTopic.new_users: 16749490,  # pink
    ReportTopic.misc: 13338331,  # violet
}

# Serialize group sends and keep a minimal gap to respect Telegram's ~20
# messages/minute per-group limit under bursts (retries handle the rest).
_send_lock = asyncio.Lock()
_last_group_send = 0.0
_MIN_GAP_SECONDS = 1.1


class ReportSetupError(Exception):
    """Raised by setup_topics with a user-facing Persian message."""


def _get_settings():
    # Local import: settings imports payment plugins which import app.main —
    # importing it lazily keeps this module import-safe everywhere.
    from app.utils import settings

    return settings.get_settings()


def group_configured() -> bool:
    return bool(getattr(_get_settings(), "reports_group_id", None))


def topic_enabled(topic: ReportTopic) -> bool:
    disabled = getattr(_get_settings(), "reports_disabled_topics", []) or []
    return topic.value not in disabled


def topic_target(topic: ReportTopic) -> Optional[tuple[int, Optional[int]]]:
    """(group_id, thread_id) when the group is configured and the topic is
    enabled — for callers that send/forward on their own (e.g. receipt photo
    forwards). None = use the legacy destination."""
    _settings = _get_settings()
    group_id = getattr(_settings, "reports_group_id", None)
    if not group_id or not topic_enabled(topic):
        return None
    raw = (getattr(_settings, "reports_topics", {}) or {}).get(topic.value)
    return group_id, (int(raw) if raw else None)


def sanitize(text: str) -> str:
    """Mask secrets that must never reach a Telegram chat (errors topic)."""
    if not text:
        return text
    for secret in (config.BOT_TOKEN, config.DATABASE_URL, config.SECRET_KEY_STRING):
        if secret:
            text = text.replace(str(secret), "***")
    return text


async def _create_topic(group_id: int, topic: ReportTopic) -> Optional[int]:
    """Create one forum topic; returns its thread id or None on failure."""
    try:
        created = await bot.create_forum_topic(
            chat_id=group_id,
            name=TOPIC_TITLES[topic],
            icon_color=TOPIC_COLORS.get(topic),
        )
        return created.message_thread_id
    except Exception as exc:  # noqa: BLE001 - caller falls back to General
        logger.warning("could not create forum topic %s: %s", topic.value, exc)
        return None


async def setup_topics(group_id: int) -> dict[str, int]:
    """Validate the group and create all report topics in it.

    Used by the admin setup flow. Raises ReportSetupError with a Persian,
    user-facing message when the group is unusable. Returns the
    {topic_key: thread_id} mapping (existing usable threads are re-created
    from scratch — setup is meant for a fresh group)."""
    try:
        chat = await bot.get_chat(group_id)
    except exceptions.TelegramBadRequest:
        raise ReportSetupError(
            "چت یافت نشد! مطمئن شوید ربات عضو گروه است و آیدی عددی را درست وارد کرده‌اید."
        )
    if not getattr(chat, "is_forum", False):
        raise ReportSetupError(
            "این گروه حالت «تاپیک‌ها» (Topics) ندارد! ابتدا در تنظیمات گروه Topics را فعال کنید."
        )
    try:
        me = await bot.get_chat_member(group_id, bot.id)
    except exceptions.TelegramBadRequest:
        raise ReportSetupError("ربات عضو این گروه نیست! ابتدا ربات را به گروه اضافه کنید.")
    if getattr(me, "status", "") != "administrator" or not getattr(
        me, "can_manage_topics", False
    ):
        raise ReportSetupError(
            "ربات باید در گروه «ادمین» باشد و دسترسی «مدیریت تاپیک‌ها» (Manage Topics) داشته باشد!"
        )

    mapping: dict[str, str] = {}
    for topic in ReportTopic:
        thread_id = await _create_topic(group_id, topic)
        if thread_id is None:
            raise ReportSetupError(
                f"ساخت تاپیک «{TOPIC_TITLES[topic]}» ناموفق بود! دسترسی‌های ربات را بررسی و دوباره تلاش کنید."
            )
        # str values: the settings field is dict[str, str] (KeyValueBase JSON)
        mapping[topic.value] = str(thread_id)
    return mapping


async def _remember_thread_id(topic: ReportTopic, thread_id: Optional[int]) -> None:
    """Persist a (re)created thread id into settings and reload the cache."""
    from app.utils import settings

    topics = dict(getattr(settings.get_settings(), "reports_topics", {}) or {})
    if thread_id is None:
        topics.pop(topic.value, None)
    else:
        topics[topic.value] = str(thread_id)
    try:
        await settings.Settings.update(reports_topics=topics)
        await settings.reload_settings()
    except Exception:  # noqa: BLE001 - persistence failure must not break sends
        logger.warning("could not persist reports_topics", exc_info=True)


async def _send(
    chat_id: int | str,
    text: str,
    *,
    thread_id: Optional[int] = None,
    reply_markup=None,
    document: Optional[BufferedInputFile] = None,
    pin: bool = False,
):
    """One send with RetryAfter handling; raises TelegramBadRequest upward so
    the caller can react to a deleted topic."""
    global _last_group_send
    async with _send_lock:
        gap = _MIN_GAP_SECONDS - (time.monotonic() - _last_group_send)
        if gap > 0:
            await asyncio.sleep(gap)
        for _ in range(3):
            try:
                if document is not None:
                    msg = await bot.send_document(
                        chat_id,
                        document=document,
                        caption=text,
                        message_thread_id=thread_id,
                        reply_markup=reply_markup,
                    )
                else:
                    msg = await bot.send_message(
                        chat_id,
                        text,
                        message_thread_id=thread_id,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True,
                    )
                break
            except exceptions.TelegramRetryAfter as err:
                await asyncio.sleep(err.retry_after)
        else:
            return None
        _last_group_send = time.monotonic()
    if pin:
        try:
            await bot.pin_chat_message(
                chat_id, msg.message_id, disable_notification=True
            )
        except Exception:  # noqa: BLE001 - pinning is best-effort
            pass
    return msg


def _is_missing_thread(exc: exceptions.TelegramBadRequest) -> bool:
    msg = str(exc).lower()
    return "thread not found" in msg or "topic_deleted" in msg or "topic deleted" in msg


@bg_job
async def report(
    topic: ReportTopic,
    text: str,
    *,
    reply_markup=None,
    document: Optional[BufferedInputFile] = None,
    pin: bool = False,
    legacy_chat_id: int | str | None = None,
    legacy_super_users: bool = False,
) -> None:
    """Deliver one report. Never raises.

    ``legacy_chat_id`` / ``legacy_super_users`` describe where this category
    went BEFORE the reports group existed; they are used only when no group is
    configured (exact pre-feature behavior)."""
    try:
        _settings = _get_settings()
        group_id = getattr(_settings, "reports_group_id", None)

        if not group_id:  # legacy behavior
            if legacy_chat_id:
                await _send(legacy_chat_id, text, reply_markup=reply_markup, document=document)
            elif legacy_super_users:
                for uid in config.SUPER_USERS:
                    try:
                        await _send(uid, text, reply_markup=reply_markup, document=document)
                    except exceptions.TelegramBadRequest:
                        pass
            return

        if not topic_enabled(topic):
            return

        topics = getattr(_settings, "reports_topics", {}) or {}
        raw_thread = topics.get(topic.value)
        thread_id = int(raw_thread) if raw_thread else None

        try:
            await _send(
                group_id,
                text,
                thread_id=thread_id,
                reply_markup=reply_markup,
                document=document,
                pin=pin,
            )
            return
        except exceptions.TelegramBadRequest as exc:
            if not _is_missing_thread(exc):
                raise

        # Topic was deleted by an admin: re-create once, else use General.
        new_thread = await _create_topic(group_id, topic)
        await _remember_thread_id(topic, new_thread)
        await _send(
            group_id,
            text,
            thread_id=new_thread,
            reply_markup=reply_markup,
            document=document,
            pin=pin,
        )
    except Exception:  # noqa: BLE001 - reporting must never break the caller
        logger.warning("report(%s) failed", getattr(topic, "value", topic), exc_info=True)
