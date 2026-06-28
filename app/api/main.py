"""GuardinoBot web-panel API (FastAPI, §9).

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


app = FastAPI(title="GuardinoBot Web Panel API", version="0.1.0", lifespan=lifespan)

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
