from aiogram import Dispatcher
from aiohttp import web

from . import payment


def include_plugins(dp: Dispatcher, webapp: web.Application):
    payment.init_plugins(dp=dp, webapp=webapp)
