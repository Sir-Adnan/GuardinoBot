"""JWT + Telegram-OTP login primitives for the web panel.

OTP codes live in Redis with a short TTL, a resend cooldown and an attempt cap.
JWTs are HS256 signed with ``config.WEB_JWT_SECRET`` (separate from the DB
field-encryption ``SECRET_KEY_STRING``).
"""

from __future__ import annotations

import secrets
import time
from typing import Optional

import jwt

import config
from app.api.clients import redis

_ALGO = "HS256"
ACCESS_TTL = 15 * 60            # 15 minutes
REFRESH_TTL = 30 * 24 * 3600   # 30 days
OTP_TTL = 120                  # login-code lifetime (seconds)
OTP_RESEND_AFTER = 60          # min seconds between code requests
OTP_MAX_ATTEMPTS = 5           # wrong tries before a code is burned

_CODE_KEY = "web:otp:code:{uid}"
_TRIES_KEY = "web:otp:tries:{uid}"
_RL_KEY = "web:otp:rl:{uid}"


def _create(sub: int, role: int, kind: str, ttl: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(sub),
        "role": int(role),
        "type": kind,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, config.WEB_JWT_SECRET, algorithm=_ALGO)


def create_access(sub: int, role: int) -> str:
    return _create(sub, role, "access", ACCESS_TTL)


def create_refresh(sub: int, role: int) -> str:
    return _create(sub, role, "refresh", REFRESH_TTL)


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, config.WEB_JWT_SECRET, algorithms=[_ALGO])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


async def issue_otp(user_id: int) -> Optional[str]:
    """Generate + store a 6-digit code, or None if one was requested too
    recently (resend cooldown)."""
    if await redis.get(_RL_KEY.format(uid=user_id)):
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.set(_CODE_KEY.format(uid=user_id), code, ex=OTP_TTL)
    await redis.delete(_TRIES_KEY.format(uid=user_id))
    await redis.set(_RL_KEY.format(uid=user_id), "1", ex=OTP_RESEND_AFTER)
    return code


async def verify_otp(user_id: int, code: str) -> bool:
    key = _CODE_KEY.format(uid=user_id)
    stored = await redis.get(key)
    if not stored:
        return False
    tries = await redis.incr(_TRIES_KEY.format(uid=user_id))
    await redis.expire(_TRIES_KEY.format(uid=user_id), OTP_TTL)
    if tries > OTP_MAX_ATTEMPTS:
        await redis.delete(key)
        return False
    if secrets.compare_digest(stored, code):
        await redis.delete(key)
        await redis.delete(_TRIES_KEY.format(uid=user_id))
        return True
    return False
