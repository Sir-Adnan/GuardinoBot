from contextlib import contextmanager
from typing import Any, Generator

from aiogram.types import CallbackQuery, Message

from app.main import redis

TRANSACTION_LOCKS: dict[str | int, bool] = dict()


class RateLimit:
    @classmethod
    async def throttled(
        cls,
        qmsg: CallbackQuery | Message | None,
        id: int,
        key: str = "default",
        count: int = 5,
        duration: int = 10,
        limit_for: int = 8,
    ) -> bool:
        if (
            limit := await cls._check_throttled(
                id=id,
                key=key,
            )
        ) > 0:
            if qmsg is None:
                return True
            text = f"""
🛑 تعداد درخواست‌های شما زیاد است! لطفا {limit} ثانیه منتظر بمانید♻️
"""
            await qmsg.answer(text)
            return True
        await cls._set_throttle(
            id=id,
            key=key,
            count=count,
            duration=duration,
            limit_for=limit_for,
        )

        return False

    @classmethod
    async def _check_throttled(
        cls,
        id: int,
        key: str,
    ) -> int:
        """Check if user has throttled or not

        Args:
            id (int): telegram id of user
            key (str): throttling key for this handler
            count (str): how many message can send
            duration (int): duration to record count of messages
            limit_for (int): limit for this amount of seconds after throttle detected

        Returns:
            int: -2 if is not throttled, else the amount of seconds that user is limited
        """
        return await redis.ttl(f"user_limited:{key}:{id}")

    @classmethod
    async def _set_throttle(
        cls, id: int, key: str, count: int, duration: int, limit_for: int
    ) -> None:
        USER_FLOOD_KEY = f"user_flood:{key}:{id}"

        bucket = await redis.get(USER_FLOOD_KEY)

        if bucket is None:
            await redis.setex(USER_FLOOD_KEY, duration, 1)
            bucket = 1
        else:
            await redis.incrby(USER_FLOOD_KEY, 1)

        # Calculate
        if (int(bucket) + 1) >= count:
            await redis.setex(f"user_limited:{key}:{id}", limit_for, "True")


@contextmanager
def lock(user_id: int) -> Generator[None, None, None]:
    """ContextMaager to lock a value

    Args:
        user_id (int): id of the user that the operation is going to run on
    """
    try:
        TRANSACTION_LOCKS[user_id] = True
        yield
    finally:
        del TRANSACTION_LOCKS[user_id]


def is_locked(user_id: int) -> bool:
    """Checks if a user_id has been locked

    Args:
        user_id (int): id of the user to check for locks

    Returns:
        bool: True if user has been locks else False
    """
    return TRANSACTION_LOCKS.get(user_id, False)
