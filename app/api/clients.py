"""Lightweight clients for the web-panel API process.

The API runs as a *separate* process from the bot, so it must NOT import
``app.main`` (which builds the Dispatcher, scheduler and polling bot). It only
needs a Redis connection (OTP store) and a send-only Bot (to deliver login
codes). A second Bot with the same token may send messages — only *polling*
must be single-instance.
"""

from aiogram import Bot
from redis.asyncio import Redis

import config

redis = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)

# Send-only bot (no polling) used to deliver one-time login codes.
bot = Bot(token=config.BOT_TOKEN)
