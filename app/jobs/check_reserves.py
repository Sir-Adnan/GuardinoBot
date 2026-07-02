from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from tortoise.transactions import in_transaction

from app.jobs import logger
from app.keyboards.user.proxy import ProxySettings
from app.main import bot, scheduler
from app.models.proxy import Proxy, ProxyStatus, Reserve
from app.panels import PanelError, get_panel
from app.utils import helpers


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
    async with in_transaction():
        panel = get_panel(service.server_id)
        try:
            sv_proxy = await panel.reset_usage(proxy.username)
        except PanelError as exc:
            if exc.status_code == 404:
                await Reserve.filter(proxy_id=proxy.id).delete()
                await Proxy.filter(id=proxy.id).update(status=ProxyStatus.disabled)
                logger.error(
                    f"Activating reserve: {proxy.id}:{proxy.username}: proxy not found on server"
                )
                return
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: {exc.status_code} returned from server"
            )
            return
        except Exception as exc:  # noqa: BLE001 - e.g. DNS/connect errors
            # transient network / dead panel host: keep retrying on the next
            # cycle, but with a one-line log instead of a traceback storm
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: panel unreachable: {exc}"
            )
            return

        data_limit = service.data_limit
        await proxy.fetch_related("service")
        if (
            data_limit
            and proxy.service
            and proxy.service.data_limit
            and proxy.service.append_available_data_renew
        ):
            data_limit = data_limit + ((sv_proxy.data_limit or 0) - sv_proxy.used_traffic)
        if service.id != proxy.service_id:
            proxy.service_id = service.id

        # Panel-agnostic re-provisioning (Marzban: inbounds/proxies carry-over;
        # PasarGuard: group_ids). Caller fills expire/data_limit/reset.
        params = await panel.service_modify_params(service, existing=sv_proxy)
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
        sv_proxy = await panel.modify_user(proxy.username, params)
        proxy.status = sv_proxy.status.value
        await proxy.save()
        await Reserve.filter(proxy_id=proxy.id).delete()
    text = f"""
✅ پلن پشتیبان برای پروکسی <code>{proxy.username}</code> فعال شد!
"""
    await bot.send_message(
        proxy.user_id, text, reply_markup=ProxySettings(proxy=proxy).as_markup()
    )


async def check_reserves():
    soon_to_be_activated = Reserve.filter(
        activate_at__not_isnull=True, activate_at__lt=dt.now() + td(seconds=30)
    )
    if (count := await soon_to_be_activated.count()) < 1:
        return
    logger.info(f"putting {count} reserves to queue...")
    reserves = await soon_to_be_activated.all()
    for reserve in reserves:
        if scheduler.get_job(f"reserves:queue:{reserve.proxy_id}"):
            continue
        scheduler.add_job(
            activate_reserve,
            "date",
            id=f"reserves:queue:{reserve.proxy_id}",
            args=(reserve.proxy_id,),
            run_date=dt.now(UTC) + td(seconds=30),
        )


scheduler.add_job(
    check_reserves,
    "interval",
    seconds=30,
    id="check_reserves",
    replace_existing=True,
    start_date=dt.now(UTC) + td(seconds=10),
)
