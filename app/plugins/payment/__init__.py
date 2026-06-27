# ruff: noqa: E402

from aiogram import Dispatcher
from aiohttp import web

from app.logger import get_logger

logger = get_logger("plugins/payment")


from . import card_to_card, crypto, perfect_money, rial_gateway, tronseller

handlers = [
    crypto.nowpayments,
    crypto.plisio_payment,
    crypto.swapino,
    card_to_card.card_to_card,
    perfect_money.perfect_money,
    rial_gateway.auto_select,
    rial_gateway.payping,
    rial_gateway.aqaye_pardakht,
    rial_gateway.zibal,
    rial_gateway.zarinpal,
    tronseller.tronado,
]

views = [
    crypto.views,
    rial_gateway.views,
    tronseller.views,
]


def include_routers(dp: Dispatcher) -> None:
    for handler in handlers:
        logger.debug(f"Initializing Handler {handler.__name__!r}")
        if hasattr(handler, "init_handler"):
            handler.init_handler()
        dp.include_router(handler.router)
        logger.debug(f"Router '{handler.router.name}' included!")


def include_views(webapp: web.Application) -> None:
    for view in views:
        logger.debug(f"Initializing View {view.__name__!r}")
        if hasattr(view, "init_view"):
            view.init_view()
        webapp.add_routes(view.routes)
        logger.debug(f"Router '{view.__name__}' included!")


def init_plugins(dp: Dispatcher, webapp: web.Application) -> None:
    include_routers(dp)
    include_views(webapp)
