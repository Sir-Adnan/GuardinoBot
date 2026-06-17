import ssl

import aiohttp_jinja2
from aiogram import Dispatcher
from aiohttp import web
from jinja2 import FileSystemLoader

import config
from app.logger import get_logger

logger = get_logger("webapp")
webapp = web.Application()
aiohttp_jinja2.setup(webapp, loader=FileSystemLoader("app/templates"))
webapp_runner: web.TCPSite = None

ssl_context = None
if config.AIOHTTP_SSL_CERTFILE and config.AIOHTTP_SSL_KEYFILE:
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(config.AIOHTTP_SSL_CERTFILE, config.AIOHTTP_SSL_KEYFILE)


async def on_startup() -> web.TCPSite:
    from . import notifications, status

    webapp.add_routes(status.routes)
    webapp.add_routes(notifications.routes)
    runner = web.AppRunner(webapp)
    await runner.setup()
    global webapp_runner
    webapp_runner = web.TCPSite(
        runner,
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        ssl_context=ssl_context,
    )
    await webapp_runner.start()


async def on_shutdown() -> None:
    await webapp_runner.stop()


def setup_webapp(dp: Dispatcher) -> web.Application:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return webapp
