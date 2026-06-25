from aiogram import Dispatcher

from .acl import ACLMiddleware
from .button_labels import ButtonLabelMiddleware

# from .rate_limit import RateLimitMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(ACLMiddleware())
    dp.message.outer_middleware(ButtonLabelMiddleware())
    # dp.update.middleware(RateLimitMiddleware())
