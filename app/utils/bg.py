import asyncio
from functools import wraps

from app.logger import get_logger

logger = get_logger("bg_job")


def bg_job(func) -> callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> asyncio.Task:
        try:
            return asyncio.create_task(func(*args, **kwargs))
        except Exception as exc:
            logger.error(exc)

    return wrapper
