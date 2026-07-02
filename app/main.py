from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio.client import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

import config
from app.logger import get_logger

# Auto-reconnect through Redis restarts: without retry, a platform Redis
# restart turns every in-flight call into "Connection closed by server" /
# "Connection refused" until the process is restarted.
_REDIS_RETRY = dict(
    retry=Retry(ExponentialBackoff(cap=3), 5),
    retry_on_error=[RedisConnectionError, RedisTimeoutError],
    health_check_interval=30,
)

redis = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
    **_REDIS_RETRY,
)  # because it is used as the fsm_storage, it will be closed automatically on shutdown
raw_redis = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=False,
    **_REDIS_RETRY,
)  # additional redis connection that does not decode responses. has to be closed on shutdown
storage = RedisStorage(
    redis=redis,
    state_ttl=3600,
    data_ttl=3600,
)

dp = Dispatcher(storage=storage)
aiohttp_session = AiohttpSession(proxy=config.PROXY)
bot = Bot(token=config.BOT_TOKEN, session=aiohttp_session, parse_mode=config.PARSE_MODE)
bot_username = ""

scheduler = AsyncIOScheduler(
    jobstores={
        "default": RedisJobStore(
            db=config.REDIS_DB, host=config.REDIS_HOST, port=config.REDIS_PORT
        )
    },
    executors={"default": AsyncIOExecutor()},
    job_defaults={
        "coalesce": True,  # Trigger only one job to make up for missed jobs.
        "max_instances": 5,
    },
    timezone="UTC",
)

logger = get_logger("guardino-bot")


def get_bot_username() -> str:
    return bot_username


async def on_startup():
    global bot_username
    bot_username = (await bot.get_me()).username

    from app.utils import settings, texts

    await settings.reload_settings()
    await texts.reload_texts()
    scheduler.start()

    # Resume an interrupted broadcast (§17.1) from its Redis cursor, if any.
    from app.utils.broadcast import resume_pending

    await resume_pending()


async def on_shutdown():
    scheduler.shutdown()
    await raw_redis.shutdown()


def main() -> None:
    logger.info("Configuring Database...")
    from app.models import setup_database

    setup_database(dp)
    logger.info("DataBase configuration Done!")

    logger.info("Setting up webapp...")
    from app.views import setup_webapp

    webapp = setup_webapp(dp)
    logger.info("Setup webapp successfully!")

    logger.info("Configuring Plugins...")

    from app.plugins import include_plugins

    include_plugins(dp, webapp)
    logger.info("Plugin configuration Done!")

    logger.info("Configuring Routers...")
    from app.handlers import include_routers

    include_routers(dp)
    logger.info("Routers included successfully!")

    logger.info("Setting up middlewares...")
    from app.middlewares import setup_middlewares

    setup_middlewares(dp)
    logger.info("Middlewares setup successfully!")

    logger.info("Setting up API servers...")
    from app.marzban import setup_api

    setup_api(dp)
    logger.info("Setup API servers successfully!")

    logger.info("Setting up scheduled jobs...")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    logger.info("Setup scheduled jobs successfully!")

    logger.info("Starting polling for updates...")
    dp.run_polling(bot)
