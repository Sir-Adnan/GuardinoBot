"""Non-blocking, restart-resilient broadcast worker (§17.1).

One broadcast runs at a time (singleton). Its whole state lives in a Redis hash
so a restart resumes it from the last processed user instead of losing it.
Messages are re-sent **by id** (``bot.copy_message`` / ``bot.forward_message``),
not from an in-memory ``Message`` object — that is what makes resume possible
and keeps everything off the polling loop.

Public API (used by the admin handlers + startup):
    is_running() · count_recipients() · start() · cancel() · resume_pending()
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from aiogram import exceptions
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.logger import get_logger
from app.main import bot, redis
from app.models.user import User

logger = get_logger("broadcast")

_KEY = "broadcast:job"      # the single active/last job (a Redis hash)
_RATE = 25                  # global target messages/second (Telegram caps ~30)
_BATCH = 200                # users fetched per page (streamed, not all at once)
_PROGRESS_EVERY = 200       # refresh the admin progress message every N sends
_MAX_RETRY = 5              # cap RetryAfter retries per user

# Substrings meaning the recipient is unreachable → mark blocked_bot, skip on.
_BLOCKED_ERRORS = (
    "chat not found",
    "bot can't initiate conversation",
    "bot was blocked",
    "user is deactivated",
    "bots can't send messages to bots",
    "peer_id_invalid",
)


def _is_blocked_error(err: Exception) -> bool:
    s = str(err).lower()
    return any(e in s for e in _BLOCKED_ERRORS)


def _cancel_kb(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛑 لغو ارسال", callback_data=f"bcast_cancel:{job_id}")]
        ]
    )


def _build_query(svid: str, srid: str):
    q = User.filter(is_blocked=False, blocked_bot=False)
    if svid:
        q = q.filter(proxies__server_id=int(svid))
    if srid:
        q = q.filter(proxies__service_id=int(srid))
    return q.distinct()


async def is_running() -> bool:
    return (await redis.hget(_KEY, "status")) == "running"


async def count_recipients(svid: Optional[str], srid: Optional[str]) -> int:
    return await _build_query(svid or "", srid or "").count()


async def start(
    *,
    kind: str,                 # "copy" | "forward"
    from_chat_id: int,
    message_id: int,
    svid: Optional[str],
    srid: Optional[str],
    total: int,
    progress_chat: int,
    progress_msg: int,
    started_by: int,
) -> bool:
    """Create the job in Redis and launch the worker. Returns False if a
    broadcast is already running (singleton)."""
    if await is_running():
        return False
    job = {
        "id": str(int(time.time())),
        "kind": kind,
        "from_chat_id": int(from_chat_id),
        "message_id": int(message_id),
        "svid": svid or "",
        "srid": srid or "",
        "total": int(total),
        "cursor": 0,
        "success": 0,
        "fails": 0,
        "status": "running",
        "progress_chat": int(progress_chat),
        "progress_msg": int(progress_msg),
        "started_by": int(started_by),
    }
    await redis.delete(_KEY)
    await redis.hset(_KEY, mapping=job)
    asyncio.create_task(_run(job["id"]))
    return True


async def cancel(job_id: Optional[str] = None) -> bool:
    """Flag the running job as canceled. The worker stops within one message."""
    if not await is_running():
        return False
    if job_id and (await redis.hget(_KEY, "id")) != job_id:
        return False
    await redis.hset(_KEY, "status", "canceled")
    return True


async def resume_pending() -> None:
    """Startup hook: relaunch an interrupted broadcast from its saved cursor."""
    try:
        if await is_running():
            job_id = await redis.hget(_KEY, "id")
            logger.info("resuming interrupted broadcast %s", job_id)
            asyncio.create_task(_run(job_id))
    except Exception:  # noqa: BLE001 - never let a resume hiccup break startup
        logger.exception("broadcast resume failed")


async def _send_one(
    kind: str, from_chat_id: int, message_id: int, user_id: int, _tries: int = 0
) -> bool:
    """Send to one recipient by id. Handles TelegramRetryAfter (capped), marks
    blocked_bot on unreachable recipients. Returns True on success."""
    try:
        if kind == "forward":
            await bot.forward_message(user_id, from_chat_id, message_id)
        else:
            await bot.copy_message(user_id, from_chat_id, message_id)
        return True
    except exceptions.TelegramRetryAfter as err:
        if _tries >= _MAX_RETRY:
            logger.warning("broadcast: giving up on %s after %d retries", user_id, _tries)
            return False
        await asyncio.sleep(err.retry_after)
        return await _send_one(kind, from_chat_id, message_id, user_id, _tries + 1)
    except (exceptions.TelegramBadRequest, exceptions.TelegramForbiddenError) as err:
        if _is_blocked_error(err):
            await User.filter(id=user_id).update(blocked_bot=True)
        else:
            logger.warning("broadcast send failed for %s: %s", user_id, err)
        return False
    except Exception as err:  # noqa: BLE001 - one bad recipient must not stop the run
        logger.error("broadcast unknown send error for %s: %s", user_id, err)
        return False


async def _update_progress(job: dict, success: int, fails: int, total: int) -> None:
    done = success + fails
    pct = int(done / total * 100) if total else 0
    text = (
        f"📢 در حال ارسال پیام همگانی...\n\n"
        f"پیشرفت: {pct}%\n"
        f"✅ موفق: {success:,}\n"
        f"❌ ناموفق: {fails:,}\n"
        f"👥 کل: {total:,}"
    )
    try:
        await bot.edit_message_text(
            text,
            chat_id=int(job["progress_chat"]),
            message_id=int(job["progress_msg"]),
            reply_markup=_cancel_kb(job["id"]),
        )
    except Exception:  # noqa: BLE001 - progress edit is best-effort
        pass


async def _finalize(job: dict, success: int, fails: int, total: int, status: str) -> None:
    head = "🛑 ارسال پیام همگانی لغو شد!" if status == "canceled" else "✅ ارسال پیام همگانی کامل شد!"
    text = f"{head}\n\n✅ موفق: {success:,}\n❌ ناموفق: {fails:,}\n👥 کل: {total:,}"
    try:
        await bot.edit_message_text(
            text,
            chat_id=int(job["progress_chat"]),
            message_id=int(job["progress_msg"]),
        )
    except Exception:  # noqa: BLE001
        try:
            await bot.send_message(int(job["progress_chat"]), text)
        except Exception:  # noqa: BLE001
            pass


async def _run(job_id: str) -> None:
    try:
        job = await redis.hgetall(_KEY)
        if not job or job.get("id") != job_id or job.get("status") != "running":
            return
        kind = job["kind"]
        from_chat_id = int(job["from_chat_id"])
        message_id = int(job["message_id"])
        svid, srid = job.get("svid", ""), job.get("srid", "")
        total = int(job.get("total") or 0)
        cursor = int(job.get("cursor") or 0)
        success = int(job.get("success") or 0)
        fails = int(job.get("fails") or 0)
        delay = 1 / _RATE
        since_progress = 0
        await _update_progress(job, success, fails, total)  # show cancel button now

        while True:
            if (await redis.hget(_KEY, "status")) != "running":
                break
            uids = (
                await _build_query(svid, srid)
                .filter(id__gt=cursor)
                .order_by("id")
                .limit(_BATCH)
                .values_list("id", flat=True)
            )
            if not uids:
                await redis.hset(_KEY, "status", "done")
                break
            canceled = False
            for uid in uids:
                ok = await _send_one(kind, from_chat_id, message_id, uid)
                success += 1 if ok else 0
                fails += 0 if ok else 1
                cursor = uid
                await redis.hset(
                    _KEY,
                    mapping={"cursor": cursor, "success": success, "fails": fails},
                )
                since_progress += 1
                if since_progress >= _PROGRESS_EVERY:
                    since_progress = 0
                    await _update_progress(job, success, fails, total)
                await asyncio.sleep(delay)
                if (await redis.hget(_KEY, "status")) != "running":
                    canceled = True
                    break
            if canceled:
                break

        status = await redis.hget(_KEY, "status") or "done"
        await _finalize(job, success, fails, total, status)
    except Exception:  # noqa: BLE001
        logger.exception("broadcast worker crashed")
        # Mark terminal so a dead in-process worker can't wedge the singleton
        # ("running" forever). A real restart never reaches here, so its job
        # stays "running" and is resumed by resume_pending() on next boot.
        try:
            await redis.hset(_KEY, "status", "crashed")
        except Exception:  # noqa: BLE001
            pass
