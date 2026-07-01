from aiogram import F
from aiogram.filters.exception import ExceptionTypeFilter
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app import main
from app.handlers.admin.server import GetTokenError, get_token_from_username_password
from app.logger import get_logger
from app.marzban import Marzban, ServerAuthenticationError
from app.models.server import Server
from app.panels import PanelError

logger = get_logger("handlers/errors")


@main.dp.error(
    ExceptionTypeFilter(PanelError),
    F.update.callback_query.as_("qmsg") | F.update.message.as_("qmsg"),
)
async def panel_error_handler(event: ErrorEvent, qmsg: Message | CallbackQuery):
    """Safety net for PanelError/PanelAuthError raised by the adapter layer
    (PasarGuard/Guardino). Without it an unhandled panel error silently aborts
    the update — to the user it looks like "nothing happened". The raw detail is
    logged only (never shown), per the no-secret-leak rule (§11)."""
    exc = event.exception
    code = getattr(exc, "status_code", None)
    logger.warning("unhandled PanelError: %s", exc)
    text = (
        "😬 ارتباط با پنل برقرار نشد"
        + (f" (کد {code})" if code else "")
        + ".\nلطفاً اتصال، آدرس و توکن/رمز سرور را بررسی کنید و دوباره تلاش کنید."
    )
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.answer(text, show_alert=True)
    return await qmsg.answer(text)


@main.dp.error(
    ExceptionTypeFilter(ServerAuthenticationError),
    F.update.callback_query.as_("qmsg") | F.update.message.as_("qmsg"),
)
async def server_error_handler(event: ErrorEvent, qmsg: Message | CallbackQuery):
    if isinstance(event.exception, ServerAuthenticationError):
        server = await Server.get(id=event.exception.server_id)
        if server.username and server.password:
            try:
                access_token = await get_token_from_username_password(
                    server.url, server.username, server.password
                )
                await server.update_from_dict({"token": access_token}).save()
                await Marzban.refresh_servers()
            except GetTokenError as exc:
                logger.error(exc)
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.answer(
            "😬 خطایی در روند اتصال به سرور رخ داد! لطفا کمی بعد دوباره تلاش کنید (کد ۱۶)...",
            show_alert=True,
        )
    return await qmsg.answer(
        "😬 خطایی در روند اتصال به سرور رخ داد! لطفا کمی بعد دوباره تلاش کنید (کد ۱۶)...",
    )


@main.dp.error()
async def unhandled_error_handler(event: ErrorEvent):
    """Last-resort net (after the specific handlers above): log + report every
    unhandled handler exception to the reports group's errors topic. The user
    gets a generic Persian message; internals are never shown (§11) and the
    report text is sanitized (no tokens/DSN). No-op report when no group is
    configured — same as before this handler existed."""
    from app.utils import reports

    exc = event.exception
    logger.exception("unhandled error in update handler", exc_info=exc)

    # Frequent, harmless Telegram noise: log only, don't flood the errors topic.
    _noise = ("message is not modified", "query is too old", "message to edit not found")
    if any(n in str(exc).lower() for n in _noise):
        return True

    update = event.update
    qmsg = None
    tg_user = None
    where = "-"
    if update.callback_query:
        qmsg, tg_user = update.callback_query, update.callback_query.from_user
        where = f"callback: <code>{(update.callback_query.data or '')[:64]}</code>"
    elif update.message:
        qmsg, tg_user = update.message, update.message.from_user
        where = f"message: <code>{(update.message.text or update.message.content_type or '')[:64]}</code>"

    user_line = (
        f"\nکاربر: <a href='tg://user?id={tg_user.id}'>{tg_user.id}</a>"
        f" (@{tg_user.username or '-'})"
        if tg_user
        else ""
    )
    reports.report(
        reports.ReportTopic.errors,
        "⭕️ خطای هندل‌نشده در ربات!\n\n"
        f"نوع خطا: <code>{type(exc).__name__}</code>\n"
        f"متن خطا: <code>{reports.sanitize(str(exc))[:800]}</code>\n"
        f"محل: {where}{user_line}",
    )

    text = "😬 خطایی رخ داد! لطفا کمی بعد دوباره تلاش کنید."
    try:
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text, show_alert=True)
        elif qmsg is not None:
            await qmsg.answer(text)
    except Exception:  # noqa: BLE001 - answering is best-effort
        pass
    return True
