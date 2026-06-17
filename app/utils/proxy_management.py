from typing import Literal

import httpx
from aiogram.types import Message

from app.logger import get_logger
from app.main import redis
from app.marzban import Marzban
from app.models.proxy import Proxy
from app.models.service import Service
from app.utils import helpers
from marzban_client.api.user import get_users, modify_user
from marzban_client.errors import UnexpectedStatus
from marzban_client.models.user_modify import UserModify
from marzban_client.models.user_modify_inbounds import UserModifyInbounds
from marzban_client.models.user_modify_proxies import UserModifyProxies
from marzban_client.models.user_status import UserStatus

logger = get_logger("utils/proxy_management")


async def bulk_update_users(
    users: list[Proxy],
    field: Literal["data_limit", "expire"],
    action: Literal["inc", "dec"],
    by_value: int,
    message: Message,
    client: Marzban,
) -> None:
    logger.info(
        f"Bulk update job started for {len(users)} users for {field!r} to {action!r} by {helpers.hr_time(by_value, lang='en') if field == 'expire' else helpers.hr_size(by_value, lang='en')}"
    )
    success = 0
    try:
        result = await get_users.asyncio_detailed(
            client=client, username=[user.username for user in users]
        )
        for sv_user in result.parsed.users:
            modify = None
            if field == "expire":
                if not sv_user.expire or sv_user.status in [
                    UserStatus.DISABLED,
                    UserStatus.LIMITED,
                    UserStatus.ON_HOLD,
                ]:
                    continue
                if action == "dec":
                    modify = UserModify(
                        expire=sv_user.expire - by_value,
                    )
                else:
                    modify = UserModify(
                        expire=sv_user.expire + by_value,
                    )
            else:
                if not sv_user.data_limit or sv_user.status in [
                    UserStatus.DISABLED,
                    UserStatus.EXPIRED,
                    UserStatus.ON_HOLD,
                ]:
                    continue
                if action == "dec":
                    modify = UserModify(data_limit=sv_user.data_limit - by_value)
                else:
                    modify = UserModify(data_limit=sv_user.data_limit + by_value)
            if not modify:
                continue
            try:
                result = await modify_user.asyncio_detailed(
                    sv_user.username,
                    client=client,
                    body=modify,
                )
                if result.status_code in [403, 404]:
                    logger.error(
                        f"Error updating user {sv_user.username!r}: {result.status_code}"
                    )
                    continue
                success += 1
                await Proxy.filter(username=sv_user.username).update(
                    status=result.parsed.status
                )
            except UnexpectedStatus:
                continue
    except UnexpectedStatus as exc:
        await message.reply(f"خطایی از سمت سرور رخ داد: {exc.status_code}: {exc.args}")
        raise exc
    text = f"""
عملیات به پایان رسید!

تعداد کاربران ویرایش شده: {success}
"""
    await message.reply(text=text)
    logger.info(
        f"Bulk update job finished {success}/{len(users)} users updated for {field!r} to {action!r} by {helpers.hr_time(by_value, lang='en') if field == 'expire' else helpers.hr_size(by_value, lang='en')}"
    )


async def bulk_update_users_inbounds(
    users: list[Proxy],
    service: Service,
    message: Message,
    client: Marzban,
) -> None:
    inbounds = await service.get_inbounds()
    logger.info(
        f"Bulk update job started for {len(users)} users for inbounds to {inbounds!r}"
    )
    success = 0
    modify_inbounds = UserModifyInbounds.from_dict(inbounds)
    try:
        result = await get_users.asyncio_detailed(
            client=client, username=[user.username for user in users]
        )
        for sv_user in result.parsed.users:
            updated_user = UserModify()
            if (
                sv_user.data_limit_reset_strategy.value
                != service.usage_reset_strategy.value
            ):
                updated_user.data_limit_reset_strategy = (
                    service.usage_reset_strategy
                    if service.data_limit
                    else service.UsageResetStrategy.no_reset
                )
            updated_user.inbounds = modify_inbounds
            proxies = {}
            for protocol in inbounds:
                if protocol in sv_user.proxies.additional_properties:
                    proxies.update(
                        {protocol: sv_user.proxies.additional_properties.get(protocol)}
                    )
                else:
                    proxies.update({protocol: service.create_proxy_protocols(protocol)})
            updated_user.proxies = UserModifyProxies.from_dict(proxies)
            try:
                result = await modify_user.asyncio_detailed(
                    sv_user.username,
                    client=client,
                    body=updated_user,
                )
                if result.status_code in [403, 404]:
                    logger.error(
                        f"Error updating user {sv_user.username!r}: {result.status_code}"
                    )
                    continue
                success += 1
            except UnexpectedStatus:
                continue
    except UnexpectedStatus as exc:
        await message.reply(f"خطایی از سمت سرور رخ داد: {exc.status_code}: {exc.args}")
        raise exc
    except httpx.RemoteProtocolError as exc:
        await message.reply("پاسخی از سمت سرور دریافت نشد!")
        raise exc
    finally:
        await redis.delete(f"bg_jobs:apply_inbounds:{service.id}")
    text = f"""
عملیات به پایان رسید!

تعداد کاربران ویرایش شده: {success}
"""
    await message.reply(text=text)
    logger.info(
        f"Bulk update job finished {success}/{len(users)} users for inbounds to {inbounds!r}"
    )
