"""User notification system — proxy lifecycle alerts.

Scans every active server's proxies (batched ``get_users`` via the §6 adapter,
so it's panel-agnostic), and notifies the owner when their subscription is:
  - expiry   : within N days of expiring,
  - low_data : used >= X% of the limit, or <= Y GB remaining,
  - unused   : bought but never really connected after N days,
  - ended    : expired or data finished.

Dedup is self-healing via ``Proxy.notified`` (a per-type flag dict): a flag is
dropped once its condition no longer holds (e.g. after a renew), so a recovered
subscription can alert again. Sending is throttled and tolerates
``TelegramRetryAfter`` / blocked recipients, so the polling loop is never
blocked. Thresholds + per-type toggles live in settings (web panel / bot).
"""

import asyncio
from datetime import UTC
from datetime import datetime as dt

from aiogram import exceptions

from app.jobs import logger
from app.keyboards.user.proxy import alert_links_keyboard, alert_renew_keyboard
from app.main import bot, redis, scheduler
from app.models.proxy import Proxy
from app.models.user import User
from app.panels import PanelError, get_panel
from app.utils import settings, texts

# Last-run status, mirrored to the web Automation page (run-now button).
_STATUS_KEY = "alerts:status"


async def _set_status(**fields) -> None:
    try:
        await redis.hset(_STATUS_KEY, mapping={k: str(v) for k, v in fields.items()})
    except Exception:  # noqa: BLE001 — status is best-effort, never break the run
        pass

_GB = 1024**3
_PAGE = 50  # proxies fetched per panel batch (mirrors refresh_proxies)
_SEND_DELAY = 0.05  # ~20 msg/s global throttle
_UNUSED_BYTES = 50 * 1024**2  # < 50 MB counts as "never really used"
_IRAN_OFFSET = 3.5  # UTC+3:30 (Iran dropped DST in 2022) — for quiet-hours


def _fmt_data(num_bytes: int) -> str:
    if num_bytes >= _GB:
        return f"{num_bytes / _GB:.1f} گیگابایت"
    return f"{max(0, num_bytes) / (1024 ** 2):.0f} مگابایت"


def _expiry_steps(s) -> list[int]:
    """Expiry reminder thresholds in hours, loose→tight. Falls back to the
    single legacy ``notify_expiry_days`` when no pro steps are configured."""
    steps = sorted({int(h) for h in (s.notify_expiry_steps_hours or []) if int(h) > 0})
    if not steps:
        steps = [max(1, s.notify_expiry_days) * 24]
    return steps


def _base_of(flag: str) -> str:
    """Map a notified flag to its base alert type (``expiry:72`` → ``expiry``)."""
    return "expiry" if flag.startswith("expiry:") else flag


def _cadence(s, base: str) -> int:
    """Re-send interval (hours) for a base type. 0 = send once (no repeat)."""
    return max(0, int(getattr(s, f"alerts_cadence_{base}_hours", 0) or 0))


def _pick(pending: set[str]) -> str | None:
    """Highest-priority pending alert: ended > tightest expiry step > low_data > unused."""
    if "ended" in pending:
        return "ended"
    exp = [k for k in pending if k.startswith("expiry:")]
    if exp:  # the most urgent (fewest hours) step
        return min(exp, key=lambda k: int(k.split(":", 1)[1]))
    if "low_data" in pending:
        return "low_data"
    if "unused" in pending:
        return "unused"
    return None


def _in_quiet(s, now_utc) -> bool:
    """True if Iran-local time is inside the configured quiet window."""
    if not s.alerts_quiet_enabled:
        return False
    start = s.alerts_quiet_start_hour % 24
    end = s.alerts_quiet_end_hour % 24
    if start == end:
        return False
    h = (now_utc.hour + now_utc.minute / 60 + _IRAN_OFFSET) % 24
    return start <= h < end if start < end else (h >= start or h < end)


def _evaluate(proxy: Proxy, user, now_ts: int, s) -> set[str]:
    """Return the set of alert types whose condition currently holds."""
    status = str(getattr(user.status, "value", user.status))
    if status in ("disabled", "on_hold"):
        return set()

    data_limit = user.data_limit or 0
    used = user.used_traffic or 0
    expire = user.expire or 0

    ended = (
        status in ("expired", "limited")
        or (expire and expire <= now_ts)
        or (data_limit and used >= data_limit)
    )
    if ended:
        return {"ended"} if s.notify_ended_enabled else set()

    out: set[str] = set()

    if s.notify_expiry_enabled and expire:
        secs_left = expire - now_ts
        if secs_left > 0:
            # add every crossed step; the loop sends only the tightest new one
            # and marks the looser (already-passed) ones as seen.
            for h in _expiry_steps(s):
                if secs_left <= h * 3600:
                    out.add(f"expiry:{h}")

    if s.notify_low_data_enabled and data_limit:
        remaining = data_limit - used
        used_pct = used / data_limit * 100
        if used_pct >= s.notify_traffic_percent or remaining <= s.notify_data_remaining_gb * _GB:
            out.add("low_data")

    if s.notify_unused_enabled and status == "active" and used < _UNUSED_BYTES:
        created = proxy.created_at
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if (dt.now(UTC) - created).days >= s.notify_unused_days:
                out.add("unused")

    return out


def _render(alert_type: str, proxy: Proxy, user, now_ts: int):
    """Build (text, keyboard) for the chosen alert type."""
    t = texts.get_texts()
    name = proxy.display_name
    if alert_type.startswith("expiry"):
        secs_left = (user.expire or now_ts) - now_ts
        days = max(1, -(-secs_left // 86400))  # ceil, min 1 day
        return (
            texts.Texts.format(t.alert_expiry, NAME=name, DAYS_LEFT=str(days)),
            alert_renew_keyboard(proxy.id),
        )
    if alert_type == "low_data":
        remaining = max(0, (user.data_limit or 0) - (user.used_traffic or 0))
        return (
            texts.Texts.format(t.alert_low_data, NAME=name, DATA_LEFT=_fmt_data(remaining)),
            alert_renew_keyboard(proxy.id),
        )
    if alert_type == "unused":
        return (
            texts.Texts.format(t.alert_unused, NAME=name),
            alert_links_keyboard(proxy.id),
        )
    return (  # ended
        texts.Texts.format(t.alert_ended, NAME=name),
        alert_renew_keyboard(proxy.id),
    )


async def _send(user_id: int, text: str, kb) -> bool:
    try:
        await bot.send_message(user_id, text, reply_markup=kb)
        return True
    except exceptions.TelegramRetryAfter as err:
        await asyncio.sleep(err.retry_after)
        try:
            await bot.send_message(user_id, text, reply_markup=kb)
            return True
        except Exception:  # noqa: BLE001
            return False
    except exceptions.TelegramForbiddenError:
        await User.filter(id=user_id).update(blocked_bot=True)
        return False
    except exceptions.TelegramBadRequest:
        return False
    except Exception as err:  # noqa: BLE001 - one bad recipient must not stop the run
        logger.error("proxy_alerts send failed for %s: %s", user_id, err)
        return False


async def proxy_alerts(force: bool = False) -> None:
    from app.models.server import Server  # local import: avoids load-order issues

    s = settings.get_settings()
    now_utc = dt.now(UTC)
    now_iso = now_utc.isoformat(timespec="seconds")
    if not s.alerts_enabled:
        await _set_status(state="disabled", last_run=now_iso, sent=0)
        return
    # quiet hours never block a manual "run now" (force=True from the web panel)
    if not force and _in_quiet(s, now_utc):
        logger.info("proxy_alerts: quiet hours — deferring sends")
        await _set_status(state="deferred", last_run=now_iso, sent=0)
        return
    logger.info("proxy_alerts job started (force=%s)", force)
    await _set_status(state="running", last_run=now_iso, sent=0)
    now_ts = int(now_utc.timestamp())
    sent_total = 0

    servers = await Server.filter(is_enabled=True)
    for server in servers:
        panel = get_panel(server.id)
        offset = 0
        while True:
            proxies = (
                await Proxy.filter(server_id=server.id)
                .prefetch_related("user", "service")
                .offset(offset)
                .limit(_PAGE)
            )
            if not proxies:
                break
            offset += _PAGE

            by_username = {p.username: p for p in proxies}
            try:
                panel_users = await panel.get_users(list(by_username.keys()))
            except PanelError as exc:
                logger.error("proxy_alerts: server %s get_users failed: %s", server.id, exc)
                break

            for pu in panel_users:
                proxy = by_username.get(pu.username)
                if proxy is None or proxy.user_id is None:
                    continue
                owner = proxy.user
                if owner is None or owner.is_blocked or owner.blocked_bot:
                    continue

                current = _evaluate(proxy, pu, now_ts, s)
                notified = proxy.notified or {}

                # Self-heal: keep last-sent timestamps only for flags whose
                # condition still holds; drop the rest so a re-occurrence alerts
                # fresh. Legacy bool values (old {flag: true}) → epoch 1 = stale.
                kept: dict[str, int] = {}
                for f in current:
                    ts = notified.get(f)
                    if isinstance(ts, bool):
                        ts = 1 if ts else None
                    if ts is not None:
                        try:
                            kept[f] = int(ts)
                        except (TypeError, ValueError):
                            pass

                def _suppressed(f: str) -> bool:
                    ts = kept.get(f)
                    if ts is None:  # not sent in this run of the condition
                        return False
                    cad = _cadence(s, _base_of(f))
                    return True if cad == 0 else (now_ts - ts) < cad * 3600

                pending = {f for f in current if not _suppressed(f)}
                chosen = _pick(pending) if pending else None
                if chosen:
                    text, kb = _render(chosen, proxy, pu, now_ts)
                    if await _send(owner.id, text, kb):
                        kept[chosen] = now_ts
                        sent_total += 1
                        # stamp looser, already-passed expiry steps so a tighter
                        # step isn't followed by a stale "3 days left".
                        if chosen.startswith("expiry:"):
                            for f in current:
                                if f.startswith("expiry:"):
                                    kept[f] = now_ts
                        await asyncio.sleep(_SEND_DELAY)

                if kept != notified:
                    proxy.notified = kept
                    await proxy.save(update_fields=["notified"])

    logger.info("proxy_alerts job finished, sent=%d", sent_total)
    await _set_status(
        state="done",
        last_run=dt.now(UTC).isoformat(timespec="seconds"),
        sent=sent_total,
    )


scheduler.add_job(
    proxy_alerts,
    "cron",
    id="proxy_alerts",
    replace_existing=True,
    minute=0,  # hourly — "ended/limited/expiry" fires within ~1h (quiet hours
    # defer overnight sends, see _in_quiet); was twice-daily (≤10h lag).
)
