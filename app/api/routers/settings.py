"""Bot settings — a curated, safe subset. Super-admin only.

Reads/writes the ``BotSetting`` key-value table DIRECTLY: the API must not
import ``app.utils.settings`` (it pulls ``app.main`` via the payment plugins).
After a write, a Redis flag tells the bot to reload its cache — see
``app/jobs/sync_settings.py``.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import SettingsOut, SettingsUpdateIn
from app.models.setting import BotSetting
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

_BOOL = (
    "access_only",
    "referral_system",
    "reset_password_button",
    "show_connect_links_button",
    "show_test_service_in_menu",
    "phone_number_verify",
)
_INT = (
    "delete_expired_users_after_days",
    "remind_invoices_each_n_days",
    "remind_invoices_after_amount",
    "default_daily_test_services",
    "referral_discount_percent",
    "cancel_payback_fee",
    "cancel_payback_days",
    "guardino_balance_warn",
    "guardino_balance_critical",
)
_STR = ("default_username_prefix",)
_ALL = _BOOL + _INT + _STR
_DIRTY = "settings:dirty"


def _decode(key: str, raw: Optional[str]) -> Any:
    raw = raw or ""
    if key in _BOOL:
        return raw not in ("", "0", "false", "False")
    if key in _INT:
        try:
            return int(raw or 0)
        except ValueError:
            return 0
    return raw


async def _read() -> dict:
    rows = await BotSetting.filter(_key__in=list(_ALL)).values("_key", "_value")
    raw = {r["_key"]: r["_value"] for r in rows}
    return {k: _decode(k, raw.get(k)) for k in _ALL}


@router.get("", response_model=SettingsOut)
async def get_settings(
    _: User = Depends(require_role(User.Role.super_user)),
) -> SettingsOut:
    return SettingsOut(**await _read())


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdateIn,
    _: User = Depends(require_role(User.Role.super_user)),
) -> SettingsOut:
    changes = {
        k: v
        for k, v in body.model_dump(exclude_unset=True).items()
        if v is not None and k in _ALL
    }
    if changes:
        # BotSetting.update encodes per type (bool→"1"/"0", int→str, …) and only
        # touches existing rows (the bot creates them all on startup).
        await BotSetting.update(**changes)
        await redis.set(_DIRTY, "1")  # bot reloads within ~15s
    return SettingsOut(**await _read())
