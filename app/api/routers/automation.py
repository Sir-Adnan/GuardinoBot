"""Automation — live broadcast monitor + cancel (admin+).

The broadcast worker lives in the BOT process (app/utils/broadcast.py, §17.1).
We don't run it here; we only read/cancel via the SAME Redis job hash. Cancel
works cross-process because the worker re-reads ``status`` from Redis each
message and stops on anything but ``running``. Starting a broadcast stays in the
bot (it copies/forwards a real Telegram message).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import (
    AlertPreviewItem,
    AlertPreviewOut,
    AlertsStatusOut,
    BroadcastStatusOut,
    OkOut,
)
from app.models.setting import BotText
from app.models.user import User
from app.utils.audit import record_audit

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
