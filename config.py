import os
import re

from dotenv import load_dotenv

if DOTENV_PATH := os.getenv("PYTHON_DOTENV_FILE"):
    from decouple import Config, RepositoryEnv

    load_dotenv(DOTENV_PATH, override=True)
    config = Config(RepositoryEnv(DOTENV_PATH))
else:
    from decouple import config

    load_dotenv(override=True)


from app.logger import get_logger

log = get_logger(__name__)


LOG_LEVEL = config("LOG_LEVEL", default="info")

BOT_TOKEN = config("BOT_TOKEN")

# socks5h://127.0.0.1:2080
PROXY = config("PROXY", None)

WEBHOOK_BASE_URL: str = config("WEBHOOK_BASE_URL").rstrip("/")


AIOHTTP_SSL_CERTFILE = config("AIOHTTP_SSL_CERTFILE", default=None)
AIOHTTP_SSL_KEYFILE = config("AIOHTTP_SSL_KEYFILE", default=None)


# gateway payment systems
RIALGATEWAY_REWRITE_CALLBACK_URL = config(
    "RIALGATEWAY_REWRITE_CALLBACK_URL", default=None
)

ESWAP_API_URL = config("ESWAP_API_URL", default="https://eswap.ir/")
PAYPING_API_URL = config("PAYPING_API_URL", default="https://api.payping.ir/v2/")
AQAYEPARDAKHT_API_URL = config(
    "AQAYEPARDAKHT_API_URL", default="https://panel.aqayepardakht.ir/"
)
ZIBAL_API_URL = config("ZIBAL_API_URL", default="https://gateway.zibal.ir/v1/")
ZARINPAL_BASE_URL = config(
    "ZARINPAL_BASE_URL", default="https://api.zarinpal.com/pg/v4/"
)
NP_API_URL = config("NP_API_URL", default="https://api.nowpayments.io/v1")
NP_API_KEY = config("NP_API_KEY", default=None)
NP_IPN_SECRET_KEY = config("NP_IPN_SECRET_KEY", default=None)


SUPER_USERS = {
    int(uid) for uid in config("SUPER_USERS", default="").split("\n") if uid.isnumeric()
}


PARSE_MODE = config("PARSE_MODE", default="HTML")
DATABASE_URL = config(
    "DATABASE_URL", default="sqlite://db.sqlite3"
)  # example: 'mysql://user:pass@localhost:3306/db'
# example: 'sqlite:///guardino.db'

if DATABASE_URL is None:
    raise ValueError("'DATABASE_URL' environment variable has to be set!")


DEFAULT_USERNAME_PREFIX = config("DEFAULT_USERNAME_PREFIX", default="Guardino")

if not re.match(r"^(?!_)[A-Za-z0-9_]+$", DEFAULT_USERNAME_PREFIX):
    raise ValueError(
        "DEFAULT_USERNAME_PREFIX must be less than 20 characters and [0-9A-Za-z] and underscores in between"
    )

DEFAULT_DAILY_TEST_SERVICES = config(
    "DEFAULT_DAILY_TEST_ACCUOUNTS", default=1, cast=int
)

TRANSACTION_LOGS = config("TRANSACTION_LOGS", default=None)
ORDERS_LOGS = config("ORDERS_LOGS", default=None)


TORTOISE_ORM = {
    "connections": {"default": DATABASE_URL},
    "timezone": "UTC",
    "apps": {
        "models": {
            "models": [  # put rest of the models as so in the list
                "app.models.user",
                "app.models.server",
                "app.models.service",
                "app.models.setting",
                "app.models.proxy",
                "aerich.models",
            ],
            "default_connection": "default",
        },
    },
}

REDIS_HOST = config("REDIS_HOST", default="redis")
REDIS_PORT = config("REDIS_PORT", default=6379)
REDIS_DB = config("REDIS_DB", default=0)


WEBAPP_HOST = config("WEBAPP_HOST", default="127.0.0.1")
WEBAPP_PORT = config("WEBAPP_PORT", default=3333)

MARZBAN_WEBHOOK_SECRET = config("MARZBAN_WEBHOOK_SECRET", default=None)


FORCE_JOIN_CHATS = {
    chat.split("@")[0]: chat.split("@")[1]
    for chat in config("FORCE_JOIN_CHATS", default="").split("\n")
    if chat
}


DEFAULT_CHARGE_AMOUNT_LIST: list[int] = [
    20_000,
    50_000,
    75_000,
    95_000,
    130_000,
    195_000,
    275_000,
    330_000,
    400_000,
    600_000,
]

DEFAULT_CHARGE_ORDERS: list[int] = [2, 2, 2, 2, 1, 1]


# used for key encryptions to save in db, max 32 charachters
SECRET_KEY_STRING = config(
    "SECRET_KEY_STRING",
    default="SomethingVeRy-Secret-Change_ThIs",
)

if len(SECRET_KEY_STRING) > 32:
    raise ValueError("'SECRET_KEY_STRING' must be less than 64 charachters")
