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
from app.main import bot, scheduler
from app.models.proxy import Proxy
from app.models.user import User
from app.panels import PanelError, get_panel
from app.utils import settings, texts

_GB = 1024**3
_PAGE = 50  # proxies fetched per panel batch (mirrors refresh_proxies)
_SEND_DELAY = 0.05  # ~20 msg/s global throttle
_UNUSED_BYTES = 50 * 1024**2  # < 50 MB counts as "never really used"

# Alert type -> (text attribute on Texts, keyboard builder). Priority order below.
_PRIORITY = ("ended", "expiry", "low_data", "unused")


def _fmt_data(num_bytes: int) -> str:
    if num_bytes >= _GB:
        return f"{num_bytes / _GB:.1f} گیگابایت"
    return f"{max(0, num_bytes) / (1024 ** 2):.0f} مگابایت"


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
        if 0 < secs_left <= s.notify_expiry_days * 86400:
            out.add("expiry")

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
    if alert_type == "expiry":
        secs_left = (user.expire or now_ts) - now_ts
        days = max(1, -(-secs_left // 86400))  # ceil
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


async def proxy_alerts() -> None:
    from app.models.server import Server  # local import: avoids load-order issues

    s = settings.get_settings()
    if not s.alerts_enabled:
        return
    logger.info("proxy_alerts job started")
    now_ts = int(dt.now(UTC).timestamp())
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
                already = {k for k, v in (proxy.notified or {}).items() if v}

                # Self-heal: keep flags still true; send one highest-priority new one.
                new_flags = {t for t in already if t in current}
                pending = current - already
                if pending:
                    chosen = next(t for t in _PRIORITY if t in pending)
                    text, kb = _render(chosen, proxy, pu, now_ts)
                    if await _send(owner.id, text, kb):
                        new_flags.add(chosen)
                        sent_total += 1
                        await asyncio.sleep(_SEND_DELAY)

                if new_flags != already:
                    proxy.notified = {t: True for t in new_flags}
                    await proxy.save(update_fields=["notified"])

    logger.info("proxy_alerts job finished, sent=%d", sent_total)


scheduler.add_job(
    proxy_alerts,
    "cron",
    id="proxy_alerts",
    replace_existing=True,
    hour="6,16",  # twice daily (UTC) ≈ 9:30 & 19:30 Iran — daytime visibility
)
