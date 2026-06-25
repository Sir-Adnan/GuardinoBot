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
        try:
            user: types.User = data["event_from_user"]
            if await self.setup_chat(data, user):
                with self.context(user=data["user"]):
                    return await handler(event, data)
        except KeyError:
            return await handler(event, data)

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
