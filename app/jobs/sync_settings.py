from datetime import datetime as dt
from datetime import timedelta as td

from app.jobs import logger
from app.main import redis, scheduler
from app.utils import settings, texts

# Set by the web-panel API after a settings / texts write.
SETTINGS_DIRTY_KEY = "settings:dirty"  # app/api/routers/settings.py
TEXTS_DIRTY_KEY = "texts:dirty"  # app/api/routers/texts.py


async def sync_settings() -> None:
    """Reload the in-process settings/texts caches when the web panel changed
    them (the API sets a Redis flag). Cheap poll — keeps the bot in sync without
    a restart, since the API runs in a separate process and can't touch the
    bot's cached ``_settings`` / ``_texts``."""
    try:
        if await redis.get(SETTINGS_DIRTY_KEY):
            await redis.delete(SETTINGS_DIRTY_KEY)
            await settings.reload_settings()
            logger.info("settings reloaded (web-panel change)")
        if await redis.get(TEXTS_DIRTY_KEY):
            await redis.delete(TEXTS_DIRTY_KEY)
            await texts.reload_texts()
            logger.info("texts reloaded (web-panel change)")
    except Exception as exc:  # noqa: BLE001
        logger.error("sync_settings failed: %s", exc)


scheduler.add_job(
    sync_settings,
    "interval",
    seconds=15,
    id="sync_settings",
    replace_existing=True,
    start_date=dt.now() + td(seconds=15),
)
