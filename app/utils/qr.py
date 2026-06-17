import io
from datetime import datetime as dt
from hashlib import sha256
from urllib.parse import urlparse

from aiogram.types import LinkPreviewOptions
from qrcode.main import QRCode

from app.main import logger, raw_redis
from config import WEBHOOK_BASE_URL

SUB_PREVIEW = True

if (port := urlparse(WEBHOOK_BASE_URL).port) not in [None, 80, 443]:
    SUB_PREVIEW = False
    logger.warning(
        f"subscription link previews are disabled because WEBHOOK_BASE_URL port ({port}) is not on port 80 or 443"
    )


def gen_qr(text: str) -> QRCode:
    qr = QRCode(border=6)
    qr.add_data(text)
    return qr


def _encode_username(id: int, username: str, set_at: int) -> str:
    return sha256((username + str(id) + str(set_at)).encode()).hexdigest()


def _generate_key(encoded_username: str) -> str:
    return f"qr:generated:{encoded_username}"


def _generate_user_key(username: str) -> str:
    return f"ts:qr:{username}"


async def invalidate_qr_cache(id: int, username: str) -> None:
    """delete generated image cache for subscription url if exists"""
    _user_key = _generate_user_key(username)
    await raw_redis.delete(_user_key)


async def create_and_cache_qr_data(id: int, username: str, text: str) -> str:
    """Generates a qr-code image and caches it in the redis for 1 minutes

    returns the url to access this image directly
    """
    _user_key = _generate_user_key(username)
    set_at = int((await raw_redis.get(_user_key)) or dt.now().timestamp())
    encoded_username = _encode_username(id, username, set_at)
    _key = _generate_key(encoded_username)
    url = WEBHOOK_BASE_URL + f"/qr/{encoded_username}"
    if await raw_redis.exists(_key):
        return url
    _data = io.BytesIO()
    _qr = gen_qr(text)
    _qr.make_image().save(_data, format="PNG")
    _data.seek(0)
    await raw_redis.set(_key, _data.getvalue(), 60)
    await raw_redis.set(_user_key, set_at, 60)
    return url


async def subscription_link_preview(
    id: int, username: str, subscription_url: str
) -> LinkPreviewOptions | None:
    if not SUB_PREVIEW:
        return
    try:
        url = await create_and_cache_qr_data(id, username, subscription_url)
        logger.info(url)
        return LinkPreviewOptions(
            is_disabled=False,
            url=url,
            prefer_large_media=True,
        )
    except Exception as err:
        logger.error(err)
        return
