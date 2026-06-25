import asyncio
from functools import wraps

from app.logger import get_logger

logger = get_logger("bg_job")


def bg_job(func) -> callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> asyncio.Task | None:
        try:
            task = asyncio.create_task(func(*args, **kwargs))
        except Exception as exc:
            logger.error(exc)
            return None

        def _log_exception(
            t: asyncio.Task, _name=getattr(func, "__name__", "bg_job")
        ) -> None:
            # Surface errors raised *inside* the task; otherwise a failed
            # fire-and-forget job (e.g. service activation after payment) is
            # swallowed until the task is garbage-collected.
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                logger.error("background job %s failed: %r", _name, exc, exc_info=exc)

        task.add_done_callback(_log_exception)
        return task

    return wrapper
