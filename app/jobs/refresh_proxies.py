from datetime import UTC
from datetime import datetime as dt

from app.jobs import logger
from app.main import scheduler
from app.marzban import Marzban
from app.models.proxy import Proxy
from app.models.server import Server
from app.utils import settings
from marzban_client.api.user import get_users, remove_user
from marzban_client.errors import UnexpectedStatus
from marzban_client.models.user_status import UserStatus


async def refresh_servers() -> None:
    logger.info("refresh_servers job started")
    servers = await Server.all()
    _settings = settings.get_settings()
    for server in servers:
        not_found_on_server = list()
        logger.info(f"refreshing server {server.id}: {server.identifier}")
        client = Marzban.get_server(server.id)
        offset = 0
        limit = 50
        q = Proxy.filter(server_id=server.id).offset(offset).limit(limit)
        total = 0
        while prs := await q.all().values_list("username", flat=True):
            offset += limit
            q = q.offset(offset)
            try:
                sv_prs = await get_users.asyncio_detailed(client=client, username=prs)
                if isinstance(sv_prs, get_users.HTTPValidationError):
                    logger.error(f"Error: {sv_prs}")
                    continue
                for user in sv_prs.parsed.users:
                    prs.remove(user.username)
                    if (  # delete user if expired more than n days ago
                        _settings.delete_expired_users_after_days > 0
                        and user.expire
                        and (
                            (dt.now(UTC) - dt.fromtimestamp(user.expire, UTC)).days
                            > _settings.delete_expired_users_after_days
                        )
                    ):
                        await remove_user.asyncio(username=user.username, client=client)
                        await Proxy.filter(username=user.username).delete()
                        logger.info(
                            f"Delete Expired user after {_settings.delete_expired_users_after_days} days: {user.username}"
                        )
                        total += 1
                        continue

                    await Proxy.filter(username=user.username).update(
                        status=user.status
                    )
                if prs:
                    not_found_on_server.extend(prs)
            except UnexpectedStatus as exc:
                logger.error(
                    f"Could not refresh proxies of server {server.id}: {exc.status_code}"
                )
                break
        logger.info(f"Total users Deleted: {total}")
        logger.info(f"Users not found in server {server.id!r}: {not_found_on_server}")
    logger.info("refresh_servers job finished")


scheduler.add_job(
    refresh_servers,
    "cron",
    id="refresh_servers",
    replace_existing=True,
    hour=1,  # 1 A.M. UTC => 4:30 A.M. Iran time
)
