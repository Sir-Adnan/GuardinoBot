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
