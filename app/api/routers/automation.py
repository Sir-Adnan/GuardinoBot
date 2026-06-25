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
from app.api.schemas import BroadcastStatusOut, OkOut
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/automation", tags=["automation"])

# Mirrors app.utils.broadcast._KEY (kept local — the API must not import
# app.utils.broadcast, which pulls app.main / the Dispatcher).
_KEY = "broadcast:job"


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
