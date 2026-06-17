import re
from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from app.keyboards import base
from app.main import bot
from app.middlewares.acl import current_user
from app.models.service import Service
from app.models.user import User
from app.utils import helpers, settings, texts


class IsSuperUser(Filter):
    async def __call__(self, message: Message) -> bool:
        return current_user.get().role == User.Role.super_user


class AdminAccess(Filter):
    async def __call__(self, message: Message) -> Any:
        return current_user.get().role >= User.Role.admin


class ResellerAccess(Filter):
    async def __call__(self, message: Message) -> Any:
        return current_user.get().role >= User.Role.reseller


class IsJoinedToChannel(Filter):
    def __init__(self, send_alert: bool = True) -> None:
        self.send_alert = send_alert

    async def __call__(self, message: Message) -> bool:
        user = current_user.get()
        if user.force_join_check and (
            dt.now() - user.force_join_check.replace(tzinfo=None)
        ) < td(hours=24):
            return True
        _settings = settings.get_settings()
        if not _settings.force_join_chats:
            return True
        if await helpers.check_force_join(
            user=user, force_join_chats=_settings.force_join_chats
        ):
            return True
        if self.send_alert:
            await bot.send_message(
                user.id,
                texts.get_texts().force_join.value,
                reply_markup=base.ForceJoin(
                    force_join_chats=_settings.force_join_chats
                ).as_markup(),
            )
        return False


class HasAccess(Filter):
    async def __call__(self, qmsg: Message) -> bool:
        if settings.get_settings().access_only:
            user = current_user.get()
            if (user.role < User.Role.admin) and not user.parent_id:
                return False
        return True


class IsTestServiceName(Filter):
    async def __call__(self, message: Message, *args: Any, **kwds: Any) -> Any:
        if not settings.get_settings().show_test_service_in_menu:
            return False
        services = await Service.filter(is_test_service=True).all()
        for service in services:
            if message.text == service.display_name:
                return {"service_id": service.id}
        return False


SUBSCRIPTION_RE = re.compile(
    r"(?<=/[Ss][Uu][Bb]/)(([\w-]+\.[\w-]+\.[\w-]+)|([a-zA-Z0-9]?(?:[A-Za-z0-9_-]{4})*(?:[A-Za-z0-9_-][AQgw]|[A-Za-z0-9_-]{2}[AEIMQUYcgkosw048])?(.{10})))$"
)


class IsSubscriptionURL(Filter):
    async def __call__(self, message: Message, *args: Any, **kwds: Any) -> Any:
        if message.text and (match := SUBSCRIPTION_RE.search(message.text)):
            return {"token": match.group(0)}


class PhoneNumberVerified(Filter):
    async def __call__(self, qmsg: Message | CallbackQuery) -> bool:
        if settings.get_settings().phone_number_verify:
            user = current_user.get()
            # if (user.role >= User.Role.admin) or user.is_verified:
            if user.is_verified:
                return True
            return False
        return True
