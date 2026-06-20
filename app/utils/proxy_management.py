from typing import Literal

from aiogram.types import Message

from app.logger import get_logger
from app.main import redis
from app.models.proxy import Proxy, ProxyStatus
from app.models.service import Service
from app.panels import BasePanel, ModifyUserParams, PanelError, PanelUserStatus
from app.utils import helpers

logger = get_logger("utils/proxy_management")


async def bulk_update_users(
    users: list[Proxy],
    field: Literal["data_limit", "expire"],
    action: Literal["inc", "dec"],
    by_value: int,
    message: Message,
    panel: BasePanel,
) -> None:
    logger.info(
        f"Bulk update job started for {len(users)} users for {field!r} to {action!r} by {helpers.hr_time(by_value, lang='en') if field == 'expire' else helpers.hr_size(by_value, lang='en')}"
    )
    success = 0
    try:
        sv_users = await panel.get_users([user.username for user in users])
    except PanelError as exc:
        await message.reply(f"خطایی از سمت سرور رخ داد: {exc.status_code}: {exc.args}")
        raise exc

    for sv_user in sv_users:
        if field == "expire":
            if not sv_user.expire or sv_user.status in (
                PanelUserStatus.disabled,
                PanelUserStatus.limited,
                PanelUserStatus.on_hold,
            ):
                continue
            new_value = sv_user.expire - by_value if action == "dec" else sv_user.expire + by_value
            params = ModifyUserParams(expire=new_value)
        else:
            if not sv_user.data_limit or sv_user.status in (
                PanelUserStatus.disabled,
                PanelUserStatus.expired,
                PanelUserStatus.on_hold,
            ):
                continue
            new_value = (
                sv_user.data_limit - by_value if action == "dec" else sv_user.data_limit + by_value
            )
            params = ModifyUserParams(data_limit=new_value)

        try:
            updated = await panel.modify_user(sv_user.username, params)
        except PanelError as exc:
            logger.error(f"Error updating user {sv_user.username!r}: {exc.status_code}")
            continue
        success += 1
        await Proxy.filter(username=sv_user.username).update(
            status=ProxyStatus(updated.status.value)
        )

    await message.reply(
        text=f"""
عملیات به پایان رسید!

تعداد کاربران ویرایش شده: {success}
"""
    )
    logger.info(
        f"Bulk update job finished {success}/{len(users)} users updated for {field!r} to {action!r} by {helpers.hr_time(by_value, lang='en') if field == 'expire' else helpers.hr_size(by_value, lang='en')}"
    )


async def bulk_update_users_inbounds(
    users: list[Proxy],
    service: Service,
    message: Message,
    panel: BasePanel,
) -> None:
    logger.info(f"Bulk inbound/group update job started for {len(users)} users of service {service.id}")
    success = 0
    desired_reset = (
        service.usage_reset_strategy.value
        if service.data_limit
        else service.UsageResetStrategy.no_reset.value
    )
    try:
        sv_users = await panel.get_users([user.username for user in users])
        for sv_user in sv_users:
            # Panel-agnostic network re-provisioning (Marzban inbounds/proxies
            # carry-over, PasarGuard group_ids).
            params = await panel.service_modify_params(service, existing=sv_user)
            if sv_user.data_limit_reset_strategy != desired_reset:
                params.data_limit_reset_strategy = desired_reset
            try:
                await panel.modify_user(sv_user.username, params)
            except PanelError as exc:
                logger.error(
                    f"Error updating user {sv_user.username!r}: {exc.status_code}"
                )
                continue
            success += 1
    except PanelError as exc:
        await message.reply(f"خطایی از سمت سرور رخ داد: {exc.status_code}: {exc.args}")
        raise exc
    finally:
        await redis.delete(f"bg_jobs:apply_inbounds:{service.id}")

    await message.reply(
        text=f"""
عملیات به پایان رسید!

تعداد کاربران ویرایش شده: {success}
"""
    )
    logger.info(
        f"Bulk inbound/group update job finished {success}/{len(users)} users of service {service.id}"
    )
