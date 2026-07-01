"""Guardino-Bot web-panel API (FastAPI, §9).

A separate service beside the bot, sharing the same DB/Redis and the §6 adapter
layer. Auth is Telegram one-time-code → JWT. Run with:

    uvicorn app.api.main:app --host 0.0.0.0 --port 8000

Migrations are owned by the bot service (prestart.sh); this app never creates
schema (``generate_schemas=False``).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

import config
from app.api.clients import bot, redis
from app.api.routers import (
    audit,
    auth,
    automation,
    buttons,
    dashboard,
    discounts,
    menus,
    payment_gateways,
    proxies,
    reports,
    resellers,
    servers,
    services,
    settings,
    texts,
    transactions,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init Tortoise HERE, not via register_tortoise: a custom lifespan replaces
    # the on_event("startup") handlers register_tortoise relies on, so its init
    # would never run and every DB query would fail. Migrations stay with the
    # bot (prestart.sh); we only open connections (no schema generation).
    await Tortoise.init(config=config.TORTOISE_ORM)
    try:
        yield
    finally:
        await Tortoise.close_connections()
        try:
            await bot.session.close()
        except Exception:
            pass
        try:
            await redis.aclose()
        except Exception:
            pass


app = FastAPI(title="Guardino-Bot Web Panel API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def report_unhandled_exception(request, exc):
    """500s → the reports group's errors topic (best-effort, sanitized).

    Self-contained on purpose: this process must not import ``app.main``, so it
    can't use app.utils.reports; it reads the group/topic straight from the
    bot_settings key-value rows and sends with the API's own send-only bot."""
    import json as _json
    import logging

    from fastapi.responses import JSONResponse

    logging.getLogger("api/errors").exception("unhandled API error", exc_info=exc)
    try:
        from app.models.setting import BotSetting

        group_row = await BotSetting.filter(_key="reports_group_id").first()
        group_id = int(group_row._value) if group_row and group_row._value else None
        if group_id:
            topics_row = await BotSetting.filter(_key="reports_topics").first()
            disabled_row = await BotSetting.filter(
                _key="reports_disabled_topics"
            ).first()
            topics = _json.loads(topics_row._value) if topics_row and topics_row._value else {}
            disabled = (
                _json.loads(disabled_row._value)
                if disabled_row and disabled_row._value
                else []
            )
            if "errors" not in disabled:
                detail = str(exc)
                for secret in (config.BOT_TOKEN, config.DATABASE_URL):
                    if secret:
                        detail = detail.replace(str(secret), "***")
                thread = topics.get("errors")
                await bot.send_message(
                    group_id,
                    "⭕️ خطای هندل‌نشده در پنل وب!\n\n"
                    f"مسیر: <code>{request.method} {request.url.path}</code>\n"
                    f"نوع خطا: <code>{type(exc).__name__}</code>\n"
                    f"متن خطا: <code>{detail[:800]}</code>",
                    message_thread_id=int(thread) if thread else None,
                    parse_mode="HTML",
                )
    except Exception:  # noqa: BLE001 - reporting must never mask the 500
        pass
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

_origins = (
    ["*"]
    if config.WEB_CORS_ORIGINS.strip() == "*"
    else [o.strip() for o in config.WEB_CORS_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,  # Bearer tokens in the Authorization header, no cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router in (
    auth.router,
    dashboard.router,
    users.router,
    servers.router,
    services.router,
    proxies.router,
    transactions.router,
    reports.router,
    resellers.router,
    discounts.router,
    automation.router,
    settings.router,
    payment_gateways.router,
    texts.router,
    menus.router,
    buttons.router,
    audit.router,
):
    app.include_router(_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
