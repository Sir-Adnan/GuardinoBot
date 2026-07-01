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
from app.api.schemas import (
    ForceJoinChat,
    ForceJoinOut,
    ForceJoinUpdateIn,
    SettingsOut,
    SettingsUpdateIn,
)
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


_FJ_KEY = "force_join_chats"


async def _read_fj() -> dict:
    rows = await BotSetting.filter(_key=_FJ_KEY).values("_value")
    raw = (rows[0]["_value"] if rows else "") or ""
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


@router.get("/force-join", response_model=ForceJoinOut)
async def get_force_join(
    _: User = Depends(require_role(User.Role.super_user)),
) -> ForceJoinOut:
    d = await _read_fj()
    return ForceJoinOut(
        chats=[ForceJoinChat(id=str(k), username=str(v)) for k, v in d.items()]
    )


@router.put("/force-join", response_model=ForceJoinOut)
async def update_force_join(
    body: ForceJoinUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> ForceJoinOut:
    """Replace the forced-join channel set. `id` (chat id or @username) is what
    the membership check uses; `username` (no @) builds the join link."""
    chats: dict[str, str] = {}
    for c in body.chats:
        cid = (c.id or "").strip()
        uname = (c.username or "").strip().lstrip("@")
        if cid and uname:
            chats[cid] = uname
    await BotSetting.update(**{_FJ_KEY: chats})  # dict → JSON in the DB
    await redis.set(_DIRTY, "1")
    await record_audit(
        action="settings.force_join",
        actor=actor,
        target_type="settings",
        detail={"count": len(chats)},
    )
    return ForceJoinOut(
        chats=[ForceJoinChat(id=k, username=v) for k, v in chats.items()]
    )


# --- Topics-group reporting (app/utils/reports.py) ---------------------------
# The API process can't import app.utils.reports (→ app.main), so topic keys +
# Persian titles are mirrored here — keep in sync with reports.ReportTopic.

from pydantic import BaseModel, Field  # noqa: E402

REPORT_TOPICS: list[tuple[str, str]] = [
    ("financial", "💰 گزارش مالی"),
    ("orders", "🛍 گزارش خرید و تمدید"),
    ("test_accounts", "🔑 اکانت تست"),
    ("backup", "🤖 بکاپ ربات"),
    ("nightly", "🌙 گزارش شبانه"),
    ("errors", "❌ گزارش خطاها"),
    ("new_users", "🎉 کاربران جدید"),
    ("misc", "⚙️ سایر گزارشات"),
]
_TOPIC_KEYS = {k for k, _ in REPORT_TOPICS}
# Consumed by the bot's 15s sync poll — app/jobs/sync_settings.py.
REPORTS_ACTIONS_KEY = "reports:web:actions"


class ReportTopicOut(BaseModel):
    key: str
    title: str
    thread_id: Optional[int] = None
    enabled: bool = True


class ReportsGroupOut(BaseModel):
    connected: bool
    group_id: Optional[int] = None
    topics: list[ReportTopicOut]
    backup_interval_hours: int = 0
    nightly_report_enabled: bool = True


class ReportsGroupUpdateIn(BaseModel):
    disabled_topics: Optional[list[str]] = None
    backup_interval_hours: Optional[int] = Field(default=None, ge=0, le=24)
    nightly_report_enabled: Optional[bool] = None
    disconnect: bool = False


class ReportsTestIn(BaseModel):
    action: str  # "topic" | "nightly" | "backup"
    topic: Optional[str] = None


async def _kv(key: str) -> str:
    row = await BotSetting.filter(_key=key).values("_value")
    return (row[0]["_value"] if row else "") or ""


async def _read_reports_group() -> ReportsGroupOut:
    raw_gid = await _kv("reports_group_id")
    try:
        group_id = int(raw_gid) if raw_gid not in ("", "0") else None
    except ValueError:
        group_id = None
    try:
        topics_map = json.loads(await _kv("reports_topics") or "{}")
    except ValueError:
        topics_map = {}
    try:
        disabled = json.loads(await _kv("reports_disabled_topics") or "[]")
    except ValueError:
        disabled = []
    try:
        backup_h = int(await _kv("backup_interval_hours") or 0)
    except ValueError:
        backup_h = 0
    nightly = await _kv("nightly_report_enabled") not in ("", "0", "false", "False")
    return ReportsGroupOut(
        connected=bool(group_id),
        group_id=group_id,
        topics=[
            ReportTopicOut(
                key=k,
                title=title,
                thread_id=int(topics_map[k]) if topics_map.get(k) else None,
                enabled=k not in disabled,
            )
            for k, title in REPORT_TOPICS
        ],
        backup_interval_hours=backup_h,
        nightly_report_enabled=nightly,
    )


@router.get("/reports-group", response_model=ReportsGroupOut)
async def get_reports_group(
    _: User = Depends(require_role(User.Role.super_user)),
) -> ReportsGroupOut:
    return await _read_reports_group()


@router.patch("/reports-group", response_model=ReportsGroupOut)
async def update_reports_group(
    body: ReportsGroupUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> ReportsGroupOut:
    changes: dict = {}
    if body.disconnect:
        changes["reports_group_id"] = None
        changes["reports_topics"] = {}
    if body.disabled_topics is not None:
        bad = [k for k in body.disabled_topics if k not in _TOPIC_KEYS]
        if bad:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown topics: {bad}"
            )
        changes["reports_disabled_topics"] = body.disabled_topics
    if body.backup_interval_hours is not None:
        changes["backup_interval_hours"] = body.backup_interval_hours
    if body.nightly_report_enabled is not None:
        changes["nightly_report_enabled"] = body.nightly_report_enabled
    if changes:
        await BotSetting.update(**changes)
        await redis.set(_DIRTY, "1")  # bot reloads within ~15s
        await record_audit(
            action="settings.reports_group",
            actor=actor,
            target_type="settings",
            detail={"changed": list(changes)},
        )
    return await _read_reports_group()


@router.post("/reports-group/test")
async def test_reports_group(
    body: ReportsTestIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> dict:
    """Queue a test action; the BOT process executes it within ~15s (the API
    must not send via the reports pipeline itself — different process)."""
    current = await _read_reports_group()
    if not current.connected:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "هنوز گروه گزارشاتی متصل نشده است."
        )
    if body.action == "topic":
        if body.topic not in _TOPIC_KEYS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown topic")
        item = {"action": "test_topic", "topic": body.topic, "by": actor.id}
    elif body.action in ("nightly", "backup"):
        item = {"action": body.action, "by": actor.id}
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown action")
    await redis.rpush(REPORTS_ACTIONS_KEY, json.dumps(item))
    await record_audit(
        action="settings.reports_test",
        actor=actor,
        target_type="settings",
        detail=item,
    )
    return {"queued": True}
