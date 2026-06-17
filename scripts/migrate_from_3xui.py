"""This script should be used in production with very much care"""

import asyncio
import re
from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

import asyncmy
import httpx
from tortoise.transactions import in_transaction

from app import models
from app.models.proxy import Proxy
from app.models.user import ByAdminPayment, Transaction, User
from marzban_client.api.user import add_user, get_user
from marzban_client.client import AuthenticatedClient
from marzban_client.models.user_create import UserCreate
from marzban_client.models.user_create_inbounds import UserCreateInbounds
from marzban_client.models.user_create_proxies import UserCreateProxies
from marzban_client.models.user_status import UserStatus

SERVER_USERNAME = ""
SERVER_PASSWORD = ""

INBOUNDS = UserCreateInbounds.from_dict(
    {"vless": ["germany ws", "finland ws", "england ws"]}
)
PROTOCOLS = UserCreateProxies.from_dict({"vless": {"flow": ""}})
ON_HOLD_TIMEOUT = dt.now(UTC) + td(days=10)

marzcl = AuthenticatedClient(
    "",
    token="",
    raise_on_unexpected_status=True,
)


async def run():
    pool = await asyncmy.create_pool(
        host="127.0.0.1", port=33061, user="", password="", db=""
    )
    try:
        await models.on_startup()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT id, panel_url from server_info;")
                servers = await cursor.fetchall()
                for server in servers:
                    server_id = server[0]
                    await cursor.execute(
                        f"SELECT userid, remark, amount FROM fl_order WHERE server_id={server_id} AND status=1"
                    )
                    orders = await cursor.fetchall()
                    async with httpx.AsyncClient(timeout=30) as client:
                        url = server[1]
                        # login
                        await client.post(
                            f"{url}/login",
                            data=f"username={SERVER_USERNAME}&password={SERVER_PASSWORD}",
                            headers={
                                "Accept": "*/*",
                                "Content-Type": "application/x-www-form-urlencoded",
                            },
                        )
                        for order in orders:
                            # fetch user info
                            proxy_username = order[1]
                            try:
                                resp = await client.get(
                                    f"{url}/panel/api/inbounds/getClientTraffics/{proxy_username}",
                                    headers={"Accept": "application/json"},
                                )
                            except httpx.RemoteProtocolError:
                                resp = await client.get(
                                    f"{url}/panel/api/inbounds/getClientTraffics/{proxy_username}",
                                    headers={"Accept": "application/json"},
                                )
                            print(f"Fetching proxy {proxy_username}")
                            remote_order = resp.json().get("obj")
                            if not remote_order:
                                continue
                            user = await User.filter(id=order[0]).first()
                            if not user:
                                await cursor.execute(
                                    f"SELECT userid, name, username, wallet FROM fl_user WHERE userid={order[0]}"
                                )
                                ou = await cursor.fetchone()
                                user = await User.create(
                                    id=ou[0],
                                    username=ou[2],
                                    name=ou[1],
                                )
                                if ou[3] > 0:
                                    transaction = await Transaction.create(
                                        type=Transaction.PaymentType.by_admin,
                                        status=Transaction.Status.finished,
                                        amount=ou[3],
                                        amount_paid=ou[3],
                                        user=user,
                                    )
                                    await ByAdminPayment.create(
                                        by_admin_id=669706429, transaction=transaction
                                    )
                            proxy_username = proxy_username.replace("-", "_")
                            proxy_username = re.sub(
                                r"[^a-zA-Z0-9_]+", "", proxy_username
                            )
                            if await Proxy.filter(username=proxy_username).exists():
                                print(
                                    f"Proxy already exists! username: {proxy_username}"
                                )
                                continue
                            async with in_transaction():
                                expire = remote_order.get("expiryTime") / 1000
                                data_limit = remote_order.get("total") - (
                                    remote_order.get("up") + remote_order.get("down")
                                )
                                if data_limit < 0:
                                    print("skipping data_limit < 0")
                                    continue
                                proxy_obj = UserCreate(
                                    username=proxy_username,
                                    proxies=PROTOCOLS,
                                    inbounds=INBOUNDS,
                                    data_limit=data_limit,
                                    status=UserStatus.ON_HOLD,
                                    on_hold_expire_duration=int(
                                        expire - dt.now(UTC).timestamp()
                                    ),
                                    on_hold_timeout=ON_HOLD_TIMEOUT,
                                )

                                resp = await add_user.asyncio_detailed(
                                    client=marzcl, body=proxy_obj
                                )
                                if resp.status_code == 409:
                                    resp = await get_user.asyncio_detailed(
                                        username=proxy_username, client=marzcl
                                    )
                                sv_proxy = resp.parsed
                                proxy = await Proxy.create(
                                    username=sv_proxy.username,
                                    user_id=user.id,
                                    server_id=1,
                                )
                                print(f"Proxy created! useranme: {proxy.username}")
    finally:
        await models.on_shutdown()


if __name__ == "__main__":
    asyncio.run(run())
