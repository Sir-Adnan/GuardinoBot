"""One-tap reports-group connect.

Primary connect flow for the Topics reporting group: a super-user adds the bot
to a forum supergroup and promotes it to admin → the bot (my_chat_member)
offers an inline "connect" button right in the group → one tap validates the
group, creates the 8 report topics and saves the settings. The manual
enter-the-group-id path in setting.py stays as a fallback.

Group messages are dropped by ACLMiddleware, but my_chat_member and
callback_query updates still come through — this module relies on exactly that.
"""

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.logger import get_logger
from app.models.user import User
from app.utils import reports, settings

from . import router

logger = get_logger("handlers/admin/reports_group")

_ADMIN_STATUSES = ("administrator", "creator")


class ReportsConnectCb(CallbackData, prefix="rptcon"):
    group_id: int


@router.my_chat_member(F.chat.type.in_({"group", "supergroup"}))
async def bot_membership_changed(event: ChatMemberUpdated, user: User):
    """The bot was promoted to admin in a group by a super-user → offer the
    one-tap connect (or tell them what's missing). Silent for everyone else."""
    old = event.old_chat_member.status
    new = event.new_chat_member.status
    if new not in _ADMIN_STATUSES or old in _ADMIN_STATUSES:
        return  # not a fresh promotion
    if user.role != User.Role.super_user:
        return  # only the bot owner gets the offer

    _settings = settings.get_settings()
    already = _settings.reports_group_id == event.chat.id
    if already:
        return

    markup = InlineKeyboardBuilder()
    markup.button(
        text="🧩 اتصال به‌عنوان گروه گزارشات",
        callback_data=ReportsConnectCb(group_id=event.chat.id),
    )
    text = (
        "👋 ربات در این گروه ادمین شد!\n\n"
        "اگر می‌خواهید گزارش‌های ربات (مالی، خرید، اکانت تست، بکاپ، گزارش شبانه، "
        "خطاها و…) در تاپیک‌های همین گروه ثبت شوند، دکمه زیر را بزنید تا تاپیک‌ها "
        "به‌صورت خودکار ساخته شوند.\n\n"
        "پیش‌نیاز: حالت «تاپیک‌ها» (Topics) گروه روشن و دسترسی "
        "«Manage Topics» به ربات داده شده باشد."
    )
    if _settings.reports_group_id:
        text += (
            f"\n\n⚠️ توجه: در حال حاضر گروه <code>{_settings.reports_group_id}</code> "
            "متصل است؛ با اتصال این گروه، گروه قبلی جایگزین می‌شود."
        )
    try:
        await event.bot.send_message(
            event.chat.id, text, reply_markup=markup.as_markup()
        )
    except TelegramBadRequest as exc:
        logger.warning("connect offer failed in %s: %s", event.chat.id, exc)


@router.callback_query(ReportsConnectCb.filter())
async def connect_reports_group(
    query: CallbackQuery, user: User, callback_data: ReportsConnectCb
):
    if user.role != User.Role.super_user:
        return await query.answer(
            "فقط مدیر اصلی ربات می‌تواند گروه گزارشات را متصل کند!", show_alert=True
        )
    await query.answer("♻️ در حال بررسی گروه و ساخت تاپیک‌ها...")
    group_id = callback_data.group_id
    try:
        mapping = await reports.setup_topics(group_id)
    except reports.ReportSetupError as exc:
        try:
            return await query.message.edit_text(
                f"❌ {exc}\n\nمشکل را برطرف کنید و ربات را دوباره ادمین کنید "
                "(یا از تنظیمات ربات، اتصال دستی را بزنید)."
            )
        except TelegramBadRequest:
            return

    await settings.Settings.update(
        reports_group_id=group_id,
        reports_topics=mapping,
        reports_disabled_topics=[],
    )
    await settings.reload_settings()
    logger.info("reports group connected via one-tap: %s", group_id)

    try:
        await query.message.edit_text(
            f"✅ این گروه به‌عنوان گروه گزارشات متصل شد و {len(mapping)} تاپیک ساخته شد!\n"
            "از این پس گزارش‌های ربات در تاپیک‌های همین گروه ثبت می‌شوند.\n\n"
            "مدیریت تاپیک‌ها: تنظیمات ربات → «گروه گزارشات» یا وب‌پنل → تنظیمات."
        )
    except TelegramBadRequest:
        pass
    reports.report(
        reports.ReportTopic.misc,
        "✅ گروه گزارشات با موفقیت متصل شد!\n"
        f"👤 توسط: <a href='tg://user?id={user.id}'>{user.name or user.id}</a>",
    )
