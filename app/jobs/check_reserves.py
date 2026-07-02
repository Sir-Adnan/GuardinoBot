from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from tortoise.transactions import in_transaction

from app.jobs import logger
from app.keyboards.user.proxy import ProxySettings
from app.main import bot, redis, scheduler
from app.models.proxy import Proxy, ProxyStatus, Reserve
from app.panels import PanelError, get_panel
from app.utils import helpers

RESERVE_FAIL_KEY = "reserves:fail:{id}"
RESERVE_COOLDOWN_KEY = "reserves:cooldown:{id}"
_FAIL_ALERT_AT = 5  # consecutive failures before the one-time admin alert
_BACKOFF_BASE = 30  # seconds; doubles per consecutive failure
_BACKOFF_CAP = 3600  # never wait more than 1h between retries


def _server_label(panel) -> str:
    s = getattr(panel, "server", None)
    return (getattr(s, "name", None) or getattr(s, "host", "?")) if s else "?"


async def _register_failure(proxy: Proxy, reason: str) -> None:
    """Exponential backoff + a one-time admin alert for a reserve whose panel
    keeps failing — without this the 30s cycle retries forever at a fixed
    rate and floods the log while nobody is told."""
    fails = await redis.incr(RESERVE_FAIL_KEY.format(id=proxy.id))
    await redis.expire(RESERVE_FAIL_KEY.format(id=proxy.id), 24 * 3600)
    cooldown = min(_BACKOFF_BASE * (2 ** min(fails, 12)), _BACKOFF_CAP)
    await redis.set(RESERVE_COOLDOWN_KEY.format(id=proxy.id), "1", ex=cooldown)
    if fails == _FAIL_ALERT_AT:
        from app.utils import reports

        reports.report(
            reports.ReportTopic.misc,
            f"⚠️ فعال‌سازی پلن پشتیبان <code>{proxy.username}</code> "
            f"{fails} بار پشت‌سرهم ناموفق بود ({reason}).\n"
            "تلاش‌های بعدی با فاصله‌های طولانی‌تر (تا ۱ ساعت) ادامه می‌یابد؛ "
            "لطفاً در دسترس بودن پنلِ این سرور را بررسی کنید.",
            legacy_super_users=True,
        )


async def _clear_failures(proxy_id: int) -> None:
    await redis.delete(
        RESERVE_FAIL_KEY.format(id=proxy_id),
        RESERVE_COOLDOWN_KEY.format(id=proxy_id),
    )


async def activate_reserve(proxy_id: int) -> None:
    # One compact log line instead of a scheduler traceback every 30s — an
    # unreachable panel host or dirty data must not flood the logs forever.
    try:
        await _activate_reserve(proxy_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("activate_reserve %s failed: %s", proxy_id, exc)


async def _activate_reserve(proxy_id: int) -> None:
    proxy = await Proxy.filter(id=proxy_id).prefetch_related("reserve").first()
    if (not proxy) or (not proxy.reserve):
        return
    logger.info(f"Activating reserve {proxy.id}:{proxy.username}")

    await proxy.reserve.fetch_related("service")
    service = proxy.reserve.service
    if service is None:
        # dangling reserve (its service was deleted, e.g. restored old DB):
        # it can never activate — park it (activate_at=None stops the 30s
        # re-queue loop, the row itself is kept) and tell the admins.
        await Reserve.filter(proxy_id=proxy.id).update(activate_at=None)
        logger.error(
            f"Activating reserve: {proxy.id}:{proxy.username}: service is gone; parked"
        )
        from app.utils import reports

        reports.report(
            reports.ReportTopic.misc,
            f"⚠️ رزرو پشتیبان پروکسی <code>{proxy.username}</code> قابل فعال‌سازی "
            "نیست (سرویس آن حذف شده است) و متوقف شد. لطفا بررسی کنید.",
            legacy_super_users=True,
        )
        return
    panel = get_panel(service.server_id)

    async def _provision():
        if getattr(panel, "panel_managed_billing", False):
            # Guardino: expire/data_limit can't be modified — activation is the
            # hub's renew op (reset + recharge), exactly like renew_proxy_now.
            # The hub's RenewRequest requires days/total_gb > 0 (ceil like the
            # adapter's quote/create so billing matches the quote).
            cfg = service.panel_config or {}
            days = int(cfg.get("days") or 0)
            if not days and service.expire_duration:
                days = max(1, -(-service.expire_duration // 86400))
            total_gb = int(
                cfg.get("total_gb")
                or ((service.data_limit // (1024**3)) if service.data_limit else 0)
            )
            await panel.renew_user(
                proxy.username,
                days=days,
                total_gb=total_gb,
                pricing_mode=cfg.get("pricing_mode", "bundle"),
            )
            return await panel.get_user(proxy.username)

        sv = await panel.reset_usage(proxy.username)
        data_limit = service.data_limit
        await proxy.fetch_related("service")
        if (
            data_limit
            and proxy.service
            and proxy.service.data_limit
            and proxy.service.append_available_data_renew
        ):
            data_limit = data_limit + ((sv.data_limit or 0) - sv.used_traffic)

        # Panel-agnostic re-provisioning (Marzban: inbounds/proxies carry-over;
        # PasarGuard: group_ids). Caller fills expire/data_limit/reset.
        params = await panel.service_modify_params(service, existing=sv)
        params.expire = (
            helpers.get_expire_timestamp(service.expire_duration)
            if service.expire_duration
            else 0
        )
        params.data_limit = data_limit
        params.data_limit_reset_strategy = (
            service.usage_reset_strategy.value
            if service.data_limit
            else service.UsageResetStrategy.no_reset.value
        )
        return await panel.modify_user(proxy.username, params)

    async with in_transaction():
        try:
            sv_proxy = await _provision()
        except PanelError as exc:
            if exc.status_code == 404:
                await Reserve.filter(proxy_id=proxy.id).delete()
                await Proxy.filter(id=proxy.id).update(status=ProxyStatus.disabled)
                await _clear_failures(proxy.id)
                logger.error(
                    f"Activating reserve: {proxy.id}:{proxy.username}: proxy not found on server"
                )
                return
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: {exc.status_code} returned from server"
            )
            await _register_failure(
                proxy, f"پاسخ {exc.status_code} از پنل «{_server_label(panel)}»"
            )
            return
        except Exception as exc:  # noqa: BLE001 - e.g. DNS/connect errors
            # transient network / dead panel host: retry with backoff (not a
            # fixed 30s loop), one-line log instead of a traceback storm
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: panel unreachable: {exc}"
            )
            await _register_failure(
                proxy, f"پنل «{_server_label(panel)}» در دسترس نیست"
            )
            return

        if service.id != proxy.service_id:
            proxy.service_id = service.id
        if sv_proxy:
            proxy.status = sv_proxy.status.value
        await proxy.save()
        await Reserve.filter(proxy_id=proxy.id).delete()
    await _clear_failures(proxy.id)
    text = f"""
🎉 پلن پشتیبان اشتراک <code>{proxy.username}</code> فعال شد!

♻️ حجم و زمان سرویس شما تمدید شد؛ نیازی به تعویض لینک نیست — همان لینک اشتراک قبلی به‌صورت خودکار به‌روز شده است.
"""
    await bot.send_message(
        proxy.user_id, text, reply_markup=ProxySettings(proxy=proxy).as_markup()
    )


async def check_reserves():
    soon_to_be_activated = Reserve.filter(
        activate_at__not_isnull=True, activate_at__lt=dt.now() + td(seconds=30)
    )
    if await soon_to_be_activated.count() < 1:
        return
    queued = 0
    for reserve in await soon_to_be_activated.all():
        if scheduler.get_job(f"reserves:queue:{reserve.proxy_id}"):
            continue
        # a failing reserve inside its backoff window — don't re-queue yet
        if await redis.get(RESERVE_COOLDOWN_KEY.format(id=reserve.proxy_id)):
            continue
        scheduler.add_job(
            activate_reserve,
            "date",
            id=f"reserves:queue:{reserve.proxy_id}",
            args=(reserve.proxy_id,),
            run_date=dt.now(UTC) + td(seconds=30),
        )
        queued += 1
    if queued:
        logger.info(f"putting {queued} reserves to queue...")


scheduler.add_job(
    check_reserves,
    "interval",
    seconds=30,
    id="check_reserves",
    replace_existing=True,
    start_date=dt.now(UTC) + td(seconds=10),
)
