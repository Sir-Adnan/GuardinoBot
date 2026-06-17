from aiogram import Dispatcher

from app.logger import get_logger

logger = get_logger("handlers")

from . import admin, base, errors, prebase, start, user  # noqa: E402

handlers = [
    admin,
    prebase,
    user,
    start,
    base,
    errors,
]


def include_routers(dp: Dispatcher) -> None:
    for handler in handlers:
        logger.debug(f"Initializing Handler {handler.__name__!r}")
        if hasattr(handler, "init_handler"):
            handler.init_handler()
        if hasattr(handler, "router"):
            dp.include_router(handler.router)
            logger.debug(f"Router '{handler.router.name}' included!")
