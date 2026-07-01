from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Iterator

from aiogram import BaseMiddleware, types

import config
from app.logger import get_logger
from app.models.user import User

logger = get_logger(__name__)


current_user: ContextVar[User] = ContextVar("current_user", default=None)


class ACLMiddleware(BaseMiddleware):
    """ACL middleware for user setup"""

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        logger.debug(f"New event: {event}")
        logger.debug(f"New event data: {data}")
        # NOTE: deliberately no try/except KeyError around the handler call — a
        # KeyError raised INSIDE a handler must propagate (the old pattern
        # re-executed the whole handler, which can double-run purchases).
        user: types.User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        # The bot's conversational surface is private-chat only. In groups and
        # channels it must stay silent for plain messages (no "command not
        # found" spam / main menu in groups) and only react to inline buttons
        # (admin receipt review, reports-group connect) and to membership
        # changes (my_chat_member → reports-group connect offer).
        event_chat = data.get("event_chat")
        if (
            event_chat is not None
            and event_chat.type != "private"
            and (
                getattr(event, "message", None) is not None
                or getattr(event, "edited_message", None) is not None
            )
        ):
            return
        if await self.setup_chat(data, user):
            with self.context(user=data["user"]):
                return await handler(event, data)

    @staticmethod
    def _report_new_user(db_user: User) -> None:
        """First contact of a Telegram user -> the reports group's
        'new users' topic (fire-and-forget; no-op when no group is set)."""
        try:
            from app.utils import reports

            reports.report(
                reports.ReportTopic.new_users,
                "🎉 یک کاربر جدید ربات را استارت کرد!\n\n"
                f"نام: <b>{db_user.name or '-'}</b>\n"
                f"نام کاربری: @{db_user.username or '-'}\n"
                f"آیدی عددی: <code>{db_user.id}</code>\n"
                f"پروفایل: <a href='tg://user?id={db_user.id}'>{db_user.id}</a>",
            )
        except Exception:  # noqa: BLE001 - reporting must never break updates
            logger.warning("new-user report failed", exc_info=True)

    @contextmanager
    def context(self, user: User) -> Iterator[None]:
        """Set current_user context"""
        ctx_token = current_user.set(user)
        logger.debug(f"Setting up user with {user.id=} and {ctx_token=}")
        try:
            yield
        finally:
            logger.debug(f"Resetting user with {user.id=} and {ctx_token=}")
            current_user.reset(ctx_token)

    async def setup_chat(self, data: dict[str, Any], user: types.User) -> User | None:
        db_user = await User.filter(id=user.id).first()
        if not db_user:
            if user.id in config.SUPER_USERS:
                db_user = await User.create(
                    id=user.id,
                    username=user.username,
                    name=user.full_name,
                    role=User.Role.super_user,
                )
            else:
                db_user = await User.create(
                    id=user.id, username=user.username, name=user.full_name
                )
            self._report_new_user(db_user)
            data["user"] = db_user
            return db_user

        if db_user.is_blocked:
            return

        update = dict()
        if db_user.blocked_bot:
            update["blocked_bot"] = False
        if user.username is not None and user.username != db_user.username:
            update["username"] = user.username
        if user.full_name is not None and user.full_name != db_user.name:
            update["name"] = user.full_name
        if user.id in config.SUPER_USERS and db_user.role != User.Role.super_user:
            update["role"] = User.Role.super_user
        elif user.id not in config.SUPER_USERS and db_user.role == User.Role.super_user:
            update["role"] = User.Role.user
        if update:
            await db_user.update_from_dict(update).save()
            await db_user.refresh_from_db()

        data["user"] = db_user
        return db_user
