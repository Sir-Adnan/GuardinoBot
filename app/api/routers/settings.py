"""Bot settings — a curated, safe subset. Super-admin only.

Reads/writes the ``BotSetting`` key-value table DIRECTLY: the API must not
import ``app.utils.settings`` (it pulls ``app.main`` via the payment plugins).
After a write, a Redis flag tells the bot to reload its cache — see
``app/jobs/sync_settings.py``.
"""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import SettingsOut, SettingsUpdateIn
from app.models.setting import BotSetting
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/settings", tags=["settings"])

_BOOL = (
    "access_only",
    "referral_system",
    "reset_password_button",
    "show_connect_links_button",
    "show_test_service_in_menu",
    "purchase_show_tariffs",
    "phone_number_verify",
    "alerts_enabled",
    "notify_expiry_enabled",
    "notify_low_data_enabled",
    "notify_unused_enabled",
    "notify_ended_enabled",
    "alerts_quiet_enabled",
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
    "on_hold_timeout_seconds",
    "notify_expiry_days",
    "notify_traffic_percent",
    "notify_data_remaining_gb",
    "notify_unused_days",
    "alerts_quiet_start_hour",
    "alerts_quiet_end_hour",
)
# Plain strings + the username_generator enum (stored as its value string).
_STR = (
    "default_username_prefix",
    "username_generator",
    "transaction_logs",
    "orders_logs",
)
# JSON-encoded list[int] in the DB (BotSetting json.dumps them; the bot's
# pydantic validators read them back with validate_json).
_LIST = (
    "charge_amount_list",
    "charge_amount_orders",
    "notify_expiry_steps_hours",
)
_ALL = _BOOL + _INT + _STR + _LIST
_DIRTY = "settings:dirty"

# Fallbacks for str fields when the row is missing/empty.
_DEFAULTS = {"username_generator": "randomized"}
_USERNAME_GENERATORS = ("randomized", "incremental")


def _decode(key: str, raw: Optional[str]) -> Any:
    raw = raw or ""
    if key in _BOOL:
        return raw not in ("", "0", "false", "False")
    if key in _INT:
        try:
            return int(raw or 0)
        except ValueError:
            return 0
    if key in _LIST:
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return [int(x) for x in v] if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []
    return raw or _DEFAULTS.get(key, "")


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
    actor: User = Depends(require_role(User.Role.super_user)),
) -> SettingsOut:
    changes = {
        k: v
        for k, v in body.model_dump(exclude_unset=True).items()
        if v is not None and k in _ALL
    }
    if "username_generator" in changes and (
        changes["username_generator"] not in _USERNAME_GENERATORS
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid username_generator"
        )
    if changes:
        # BotSetting.update encodes per type (bool→"1"/"0", int→str, …) and only
        # touches existing rows (the bot creates them all on startup).
        await BotSetting.update(**changes)
        await redis.set(_DIRTY, "1")  # bot reloads within ~15s
        await record_audit(
            action="settings.update",
            actor=actor,
            target_type="settings",
            detail={"changed": changes},  # curated, non-secret keys only
        )
    return SettingsOut(**await _read())
