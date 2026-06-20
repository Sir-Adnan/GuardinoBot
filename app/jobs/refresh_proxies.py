from datetime import UTC
from datetime import datetime as dt

from app.jobs import logger
from app.main import scheduler
from app.models.proxy import Proxy, ProxyStatus
from app.models.server import Server
from app.panels import PanelError, get_panel
from app.utils import settings


async def refresh_servers() -> None:
    logger.info("refresh_servers job started")
    servers = await Server.all()
    _settings = settings.get_settings()
    for server in servers:
        not_found_on_server = list()
        logger.info(f"refreshing server {server.id}: {server.identifier}")
        panel = get_panel(server.id)
        offset = 0
        limit = 50
        q = Proxy.filter(server_id=server.id).offset(offset).limit(limit)
        total = 0
        while prs := await q.all().values_list("username", flat=True):
            offset += limit
            q = q.offset(offset)
            try:
                sv_users = await panel.get_users(prs)
                for user in sv_users:
                    prs.remove(user.username)
                    if (  # delete user if expired more than n days ago
                        _settings.delete_expired_users_after_days > 0
                        and user.expire
                        and (
                            (dt.now(UTC) - dt.fromtimestamp(user.expire, UTC)).days
                            > _settings.delete_expired_users_after_days
                        )
                    ):
                        await panel.remove_user(user.username)
                        await Proxy.filter(username=user.username).delete()
                        logger.info(
                            f"Delete Expired user after {_settings.delete_expired_users_after_days} days: {user.username}"
                        )
                        total += 1
                        continue

                    await Proxy.filter(username=user.username).update(
                        status=ProxyStatus(user.status.value)
                    )
                if prs:
                    not_found_on_server.extend(prs)
            except PanelError as exc:
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
