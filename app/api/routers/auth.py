"""Telegram one-time-code login → JWT.

Flow: POST /auth/request-code (bot DMs a 6-digit code) → POST /auth/verify
(exchange code for access+refresh JWT) → POST /auth/refresh. Only reseller+
accounts may log in.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import security
from app.api.clients import bot
from app.api.deps import get_current_user
from app.api.schemas import (
    ROLE_NAMES,
    MeOut,
    RefreshIn,
    RequestCodeIn,
    TokenOut,
    VerifyIn,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        username=user.username,
        name=user.name,
        role=int(user.role),
        role_name=ROLE_NAMES.get(int(user.role), str(int(user.role))),
    )


def _tokens(user: User) -> TokenOut:
    return TokenOut(
        access_token=security.create_access(user.id, int(user.role)),
        refresh_token=security.create_refresh(user.id, int(user.role)),
        user=_me(user),
    )


async def _resolve(identifier: str) -> Optional[User]:
    ident = (identifier or "").strip().lstrip("@")
    if not ident:
        return None
    if ident.isdigit():
        return await User.filter(id=int(ident)).first()
    return await User.filter(username__iexact=ident).first()


def _eligible(user: Optional[User]) -> bool:
    return bool(user) and not user.is_blocked and user.role >= User.Role.reseller


@router.post("/request-code")
async def request_code(body: RequestCodeIn) -> dict:
    """Send a one-time login code to the user's Telegram (if eligible). Always
    returns ok so callers can't probe which accounts exist."""
    user = await _resolve(body.identifier)
    if _eligible(user):
        code = await security.issue_otp(user.id)
        if code:
            try:
                await bot.send_message(
                    user.id,
                    "🔐 کد ورود به پنل وب گاردینو:\n\n"
                    f"<code>{code}</code>\n\n"
                    "این کد تا ۲ دقیقه معتبر است. اگر شما درخواست نداده‌اید، نادیده بگیرید.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    return {"ok": True}


@router.post("/verify", response_model=TokenOut)
async def verify(body: VerifyIn) -> TokenOut:
    user = await _resolve(body.identifier)
    if not _eligible(user) or not await security.verify_otp(user.id, body.code.strip()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "کد نامعتبر یا منقضی شده است"
        )
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn) -> TokenOut:
    try:
        payload = security.decode_token(body.refresh_token, "refresh")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است")
    user = await User.filter(id=int(payload["sub"])).first()
    if not _eligible(user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "دسترسی نامعتبر")
    return _tokens(user)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return _me(user)
