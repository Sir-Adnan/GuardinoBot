from aiogram import Dispatcher

from .acl import ACLMiddleware

# from .rate_limit import RateLimitMiddleware


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(ACLMiddleware())
    # dp.update.middleware(RateLimitMiddleware())
