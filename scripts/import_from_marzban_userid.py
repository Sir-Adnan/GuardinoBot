"""This script should be used in production with very much care"""

import asyncio

from app import models
from app.marzban import Marzban
from app.models.proxy import Proxy
from app.models.server import Server
from app.models.user import User
from marzban_client.api.user import get_users


async def run():
    try:
        await models.on_startup()

        servers = await Server.all()
        Marzban.init_servers(servers=servers)
        for server in servers:
            offset = 0
            limit = 500
            client = Marzban.get_server(id=server.id)
            while sv_prs := (
                await get_users.asyncio(client=client, offset=offset, limit=limit)
            ).users:
                offset += limit
                for pr in sv_prs:
                    if (
                        not (user_id := pr.username.split("_")[0]).isnumeric()
                        or len(user_id) < 6
                    ):
                        continue
                    user_id = int(user_id)
                    user = await User.filter(id=user_id).first()
                    if not user:
                        user = await User.create(id=user_id)
                    if await Proxy.filter(username=pr.username).exists():
                        print(f"Proxy already exists! username: {pr.username}")
                        continue
                    proxy = await Proxy.create(
                        username=pr.username,
                        user_id=user.id,
                        server_id=1,
                    )
                    print(f"Proxy created! useranme: {proxy.username}")
    finally:
        await models.on_shutdown()


if __name__ == "__main__":
    asyncio.run(run())
