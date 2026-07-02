from aiogram import Dispatcher

from .acl import ACLMiddleware
from .button_labels import ButtonLabelMiddleware

# Throttling is NOT a middleware: handlers call utils/rate_limit.RateLimit +
# lock() directly (the old RateLimitMiddleware was never registered and was
# removed).


def setup_middlewares(dp: Dispatcher) -> None:
    dp.update.outer_middleware(ACLMiddleware())
    dp.message.outer_middleware(ButtonLabelMiddleware())
