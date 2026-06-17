from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from tortoise.transactions import in_transaction

from app.jobs import logger
from app.keyboards.user.proxy import ProxySettings
from app.main import bot, scheduler
from app.marzban import Marzban
from app.models.proxy import Proxy, ProxyStatus, Reserve
from app.utils import helpers
from marzban_client.api.user import modify_user, reset_user_data_usage
from marzban_client.models.user_modify import UserModify
from marzban_client.models.user_modify_inbounds import UserModifyInbounds
from marzban_client.models.user_modify_proxies import UserModifyProxies


async def activate_reserve(proxy_id: int) -> None:
    proxy = await Proxy.filter(id=proxy_id).prefetch_related("reserve").first()
    if (not proxy) or (not proxy.reserve):
        return
    logger.info(f"Activating reserve {proxy.id}:{proxy.username}")

    await proxy.reserve.fetch_related("service")
    service = proxy.reserve.service
    async with in_transaction():
        client = Marzban.get_server(service.server_id)
        resp = await reset_user_data_usage.asyncio_detailed(
            username=proxy.username, client=client
        )
        if resp.status_code == 404:
            await Reserve.filter(proxy_id=proxy.id).delete()
            await Proxy.filter(id=proxy.id).update(status=ProxyStatus.disabled)
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: proxy not found on server"
            )
            return
        elif resp.status_code == 403:
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: 403 returned from server"
            )
            return
        sv_proxy = resp.parsed
        if not sv_proxy:
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: reset data usage didn't return anything!"
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
            data_limit = data_limit + (sv_proxy.data_limit - sv_proxy.used_traffic)
        updated_user = UserModify(
            expire=helpers.get_expire_timestamp(service.expire_duration)
            if service.expire_duration
            else 0,
            data_limit=data_limit,
            data_limit_reset_strategy=service.usage_reset_strategy
            if service.data_limit
            else service.UsageResetStrategy.no_reset,
        )
        if service.id != proxy.service_id:
            proxy.service_id = service.id
        inbounds = await service.get_inbounds()
        updated_user.inbounds = UserModifyInbounds.from_dict(inbounds)
        proxies = {}
        for protocol in inbounds:
            if protocol in sv_proxy.proxies.additional_properties:
                proxies.update(
                    {protocol: sv_proxy.proxies.additional_properties.get(protocol)}
                )
            else:
                proxies.update({protocol: service.create_proxy_protocols(protocol)})
        updated_user.proxies = UserModifyProxies.from_dict(proxies)
        sv_proxy = await modify_user.asyncio(
            username=proxy.username,
            body=updated_user,
            client=client,
        )
        proxy.status = sv_proxy.status.value
        await proxy.save()
        await Reserve.filter(proxy_id=proxy.id).delete()
        if not sv_proxy:
            logger.error(
                f"Activating reserve: {proxy.id}:{proxy.username}: modify user didn't return anything!"
            )
            return
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
