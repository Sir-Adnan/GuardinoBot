from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, types

from app.logger import get_logger
from app.main import redis

THROTTLING_COUNT = "throttling_count"
THROTTLING_DURATION = "throttling_duration"
THROTTLING_LIMIT_FOR = "throttling_limit_for"
THROTTLING_KEY = "throttling_key"
THROTTLING_MESSAGE = "throttling_message"
DEFAULT_THROTTLE_MESSAGE = (
    "تعداد درخواست‌های شما زیاد است! لطفا {limit_for} ثانیه دیگر تلاش کنید."
)


logger = get_logger(__name__)


def rate_limit(
    count: int = 5,
    duration: int = 10,
    limit_for: int = 30,
    key: str = "default",
    message: str = DEFAULT_THROTTLE_MESSAGE,
):
    """
    Decorator for configuring rate limit and key in different functions.
    :param count: how many messages
    :param duration: in what duration of time
    :param limit_for: how many seconds user be limited after throtteling
    :param key: to set different count/duration/limit_for for each function differently
    :return: callable
    """

    def decorator(func: callable):
        setattr(func, THROTTLING_COUNT, count)
        setattr(func, THROTTLING_DURATION, duration)
        setattr(func, THROTTLING_LIMIT_FOR, limit_for)
        setattr(func, THROTTLING_KEY, key)
        setattr(func, THROTTLING_MESSAGE, message)
        setattr(func, "has_limit", True)
        logger.debug(
            f"setting up rate_limits for '{func.__name__}': "
            f"{count=}, {duration=}, {limit_for=}, {key=}"
        )
        return func

    return decorator


class RateLimitMiddleware(BaseMiddleware):
    """
    Thorrettling middleware to prevent request spam from a user
    """

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: types.User = data["event_from_user"]
        if not (await self._throttled(handler=handler, event=event, user=user)):
            return await handler(event, data)

    async def _throttled(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        user: types.User,
    ) -> bool:
        """Check if user throttled or not

        Args:
            handler (Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]]): _description_
            event (types.TelegramObject): _description_
            user (types.User): _description_

        Returns:
            bool: False if user has not throttled else True
        """
        if getattr(handler, "has_limit", False):
            key = getattr(handler.func, THROTTLING_KEY, "default")
            count = getattr(handler.func, THROTTLING_COUNT, 5)
            duration = getattr(handler.func, THROTTLING_DURATION, 10)
            limit_for = getattr(handler.func, THROTTLING_LIMIT_FOR, 10)

            result = await self._check_throttled(
                user_id=user.id,
                key=key,
            )
            await self._set_throttle(
                user_id=user.id,
                count=count,
                duration=duration,
                limit_for=limit_for,
            )
            if result > 0:
                message = getattr(handler, THROTTLING_MESSAGE, DEFAULT_THROTTLE_MESSAGE)
                if message:
                    # TODO: warn user
                    pass
                return True

        return False

    async def _check_throttled(
        self,
        user_id: int,
        key: str,
    ) -> int:
        """Check if user has throttled or not

        Args:
            user_id (int): telegram id of user
            key (str): throttling key for this handler
            count (str): how many message can send
            duration (int): duration to record count of messages
            limit_for (int): limit for this amount of seconds after throttle detected

        Returns:
            int: -2 if is not throttled, else the amount of seconds that user is limited
        """
        return await redis.ttl(f"user_limited:{key}:{user_id}")

    async def _set_throttle(
        self, user_id: int, key: str, count: int, duration: int, limit_for: int
    ) -> None:
        USER_FLOOD_KEY = f"user_flood:{key}:{user_id}"

        bucket = await redis.get(USER_FLOOD_KEY)

        if bucket is None:
            await redis.setex(USER_FLOOD_KEY, duration, 1)
            bucket = 1
        else:
            await redis.incrby(USER_FLOOD_KEY, 1)

        # Calculate
        if (int(bucket) + 1) >= count:
            await redis.setex(f"user_limited:{key}:{user_id}", limit_for, "True")
