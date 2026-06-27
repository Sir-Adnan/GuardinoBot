"""Automation — live broadcast monitor + cancel (admin+).

The broadcast worker lives in the BOT process (app/utils/broadcast.py, §17.1).
We don't run it here; we only read/cancel via the SAME Redis job hash. Cancel
works cross-process because the worker re-reads ``status`` from Redis each
message and stops on anything but ``running``. Starting a broadcast stays in the
bot (it copies/forwards a real Telegram message).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import (
    AlertConfigButtonItem,
    AlertConfigOut,
    AlertConfigTextItem,
    AlertConfigUpdateIn,
    AlertPreviewItem,
    AlertPreviewOut,
    AlertsStatusOut,
    BroadcastStatusOut,
    OkOut,
)
from app.models.setting import BotSetting, BotText
from app.models.user import User
from app.utils.audit import record_audit
from app.utils.buttons import DEFAULT_STYLES, INLINE_BUTTONS, STYLE_NONE, STYLES

router = APIRouter(prefix="/automation", tags=["automation"])

# Mirrors app.utils.broadcast._KEY (kept local — the API must not import
# app.utils.broadcast, which pulls app.main / the Dispatcher).
_KEY = "broadcast:job"
# Cross-process alert trigger/status (bot side: jobs/proxy_alerts.py +
# jobs/sync_settings.py). The API only sets a flag / reads status — it must not
# import the bot's job module.
_ALERTS_RUN_KEY = "alerts:run_now"
_ALERTS_STATUS_KEY = "alerts:status"

# Sample {PLACEHOLDER} values for the alert preview (mirrors the vars each
# template supports — see app/api/routers/texts.py / app/utils/texts.py).
_ALERT_SAMPLES: dict[str, dict[str, str]] = {
    "alert_expiry": {"NAME": "آلمان ۱ (user_12345)", "DAYS_LEFT": "۲"},
    "alert_low_data": {"NAME": "آلمان ۱ (user_12345)", "DATA_LEFT": "۱.۵ گیگابایت"},
    "alert_unused": {"NAME": "آلمان ۱ (user_12345)"},
    "alert_ended": {"NAME": "آلمان ۱ (user_12345)"},
}

# Alert text keys → their {VARIABLES} (mirrors texts router). The two alert glass
# (inline) buttons + the per-type re-send cadence settings round out the config.
_ALERT_TEXT_VARS: dict[str, list[str]] = {
    "alert_expiry": ["NAME", "DAYS_LEFT"],
    "alert_low_data": ["NAME", "DATA_LEFT"],
    "alert_unused": ["NAME"],
    "alert_ended": ["NAME"],
}
_ALERT_BUTTONS = ("alert_renew", "alert_links")
_CADENCE_TYPES = ("expiry", "low_data", "unused", "ended")
_CADENCE_KEY = "alerts_cadence_{}_hours".format
_ICONS_KEY = "button_icons"
_STYLES_KEY = "button_styles"
_PREMIUM_KEY = "premium_buttons_enabled"
_SETTINGS_DIRTY = "settings:dirty"
_TEXTS_DIRTY = "texts:dirty"


async def _read_json(key: str) -> dict:
    rows = await BotSetting.filter(_key=key).values("_value")
    if not rows or not rows[0]["_value"]:
        return {}
    try:
        v = json.loads(rows[0]["_value"])
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


async def _read_int(key: str) -> int:
    rows = await BotSetting.filter(_key=key).values("_value")
    try:
        return int((rows[0]["_value"] if rows else 0) or 0)
    except (ValueError, TypeError):
        return 0


async def _read_bool(key: str) -> bool:
    rows = await BotSetting.filter(_key=key).values("_value")
    return bool(rows) and rows[0]["_value"] not in ("", "0", "false", "False", None)


@router.get("/alerts/config", response_model=AlertConfigOut)
async def alerts_config(
    _: User = Depends(require_role(User.Role.admin)),
) -> AlertConfigOut:
    rows = await BotText.filter(_key__in=list(_ALERT_TEXT_VARS)).values("_key", "_value")
    text_raw = {r["_key"]: (r["_value"] or "") for r in rows}
    icons = await _read_json(_ICONS_KEY)
    styles = await _read_json(_STYLES_KEY)
    cadence = {t: await _read_int(_CADENCE_KEY(t)) for t in _CADENCE_TYPES}
    return AlertConfigOut(
        texts=[
            AlertConfigTextItem(key=k, value=text_raw.get(k, ""), variables=v)
            for k, v in _ALERT_TEXT_VARS.items()
        ],
        buttons=[
            AlertConfigButtonItem(
                key=k,
                label=INLINE_BUTTONS.get(k, k),
                icon=str(icons.get(k) or ""),
                style=str(styles.get(k) or ""),
                default_style=DEFAULT_STYLES.get(k, ""),
            )
            for k in _ALERT_BUTTONS
        ],
        premium_enabled=await _read_bool(_PREMIUM_KEY),
        cadence=cadence,
    )


@router.patch("/alerts/config", response_model=AlertConfigOut)
async def alerts_config_update(
    body: AlertConfigUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> AlertConfigOut:
    touched_texts = False
    touched_settings = False

    # 1) alert texts → BotText (per key; empty resets to the bot default)
    if body.texts is not None:
        for k, v in body.texts.items():
            if k in _ALERT_TEXT_VARS:
                await BotText.update(**{k: v or ""})
                touched_texts = True

    # 2) button icons / styles → MERGE into the shared dicts (never clobber other
    #    buttons). Empty value removes the override (→ built-in default).
    if body.icons is not None:
        icons = await _read_json(_ICONS_KEY)
        for k, v in body.icons.items():
            if k not in _ALERT_BUTTONS:
                continue
            v = str(v or "").strip()
            if v:
                icons[k] = v
            else:
                icons.pop(k, None)
        await BotSetting.update(**{_ICONS_KEY: icons})
        touched_settings = True

    if body.styles is not None:
        styles = await _read_json(_STYLES_KEY)
        for k, v in body.styles.items():
            if k not in _ALERT_BUTTONS:
                continue
            if v in STYLES or v == STYLE_NONE:
                styles[k] = v
            else:  # "" or invalid → drop (use built-in default)
                styles.pop(k, None)
        await BotSetting.update(**{_STYLES_KEY: styles})
        touched_settings = True

    # 3) inline premium master switch
    if body.premium_enabled is not None:
        await BotSetting.update(**{_PREMIUM_KEY: bool(body.premium_enabled)})
        touched_settings = True

    # 4) per-type re-send cadence (hours, >= 0)
    if body.cadence is not None:
        for t, hrs in body.cadence.items():
            if t in _CADENCE_TYPES:
                await BotSetting.update(**{_CADENCE_KEY(t): max(0, int(hrs or 0))})
                touched_settings = True

    if touched_texts:
        await redis.set(_TEXTS_DIRTY, "1")
    if touched_settings:
        await redis.set(_SETTINGS_DIRTY, "1")
    if touched_texts or touched_settings:
        await record_audit(
            action="alerts.config", actor=actor, target_type="alerts"
        )
    return await alerts_config(actor)


@router.get("/broadcast", response_model=BroadcastStatusOut)
async def broadcast_status(
    _: User = Depends(require_role(User.Role.admin)),
) -> BroadcastStatusOut:
    job = await redis.hgetall(_KEY)
    if not job:
        return BroadcastStatusOut(status="idle")
    total = int(job.get("total") or 0)
    success = int(job.get("success") or 0)
    fails = int(job.get("fails") or 0)
    sent = success + fails
    return BroadcastStatusOut(
        status=job.get("status", "idle"),
        kind=job.get("kind"),
        total=total,
        success=success,
        fails=fails,
        sent=sent,
        progress=int(sent / total * 100) if total else 0,
        started_by=int(job["started_by"]) if job.get("started_by") else None,
    )


@router.post("/broadcast/cancel", response_model=OkOut)
async def broadcast_cancel(
    actor: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    job = await redis.hgetall(_KEY)
    if not job or job.get("status") != "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "No broadcast is running")
    await redis.hset(_KEY, "status", "canceled")
    await record_audit(
        action="broadcast.cancel",
        actor=actor,
        target_type="broadcast",
        detail={"kind": job.get("kind"), "sent": int(job.get("success") or 0)
                + int(job.get("fails") or 0)},
    )
    return OkOut(ok=True)


@router.get("/alerts", response_model=AlertsStatusOut)
async def alerts_status(
    _: User = Depends(require_role(User.Role.admin)),
) -> AlertsStatusOut:
    st = await redis.hgetall(_ALERTS_STATUS_KEY)
    if not st:
        return AlertsStatusOut(state="idle")
    return AlertsStatusOut(
        state=st.get("state", "idle"),
        last_run=st.get("last_run"),
        sent=int(st.get("sent") or 0),
    )


@router.post("/alerts/run", response_model=OkOut)
async def alerts_run_now(
    actor: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    """Ask the bot to run the proxy-alert scan immediately (bypasses quiet
    hours). The bot's 15s poll picks up the flag and runs it in the background."""
    if (await redis.hget(_ALERTS_STATUS_KEY, "state")) == "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "An alert scan is already running")
    await redis.set(_ALERTS_RUN_KEY, "1")
    await record_audit(action="alerts.run_now", actor=actor, target_type="alerts")
    return OkOut(ok=True)


@router.get("/alerts/preview", response_model=AlertPreviewOut)
async def alerts_preview(
    _: User = Depends(require_role(User.Role.admin)),
) -> AlertPreviewOut:
    """Render each alert template with sample values so the admin sees exactly
    what users receive. Reads BotText directly (no bot import); an empty row
    means the bot falls back to its built-in default."""
    rows = await BotText.filter(_key__in=list(_ALERT_SAMPLES)).values("_key", "_value")
    raw = {r["_key"]: (r["_value"] or "") for r in rows}
    items = []
    for key, sample in _ALERT_SAMPLES.items():
        tpl = raw.get(key, "")
        text = tpl
        for var, val in sample.items():
            text = text.replace("{" + var + "}", val)
        items.append(
            AlertPreviewItem(type=key, text=text.strip(), is_default=not tpl.strip())
        )
    return AlertPreviewOut(items=items)
