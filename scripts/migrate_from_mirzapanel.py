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
from app.models.server import Server
from app.models.user import ByAdminPayment, Invoice, Transaction, User
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
        host="127.0.0.1",
        port=33061,
        user="botmehdimoonm_bot",
        password="1234",
        db="botmehdimoonm_bot",
    )
    try:
        await models.on_startup()
        server = await Server.filter(id=1).first()
        if not server:
            raise ValueError("a Server with id of 1 must exist")
        admin = await User.filter(id=1977877449).first()
        if not admin:
            admin = await User.create(id=1977877449)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id, username, Balance FROM user WHERE User_Status='Active'"
                )
                users = await cursor.fetchall()
                for user in users:
                    dbuser = await User.filter(id=int(user[0])).first()
                    if not dbuser:
                        dbuser = await User.create(
                            id=user[0],
                            username=user[1],
                        )
                    else:
                        await Transaction.filter(user_id=dbuser.id).delete()
                        await Invoice.filter(user_id=dbuser.id).delete()

                        if user[2] > 0:
                            transaction = await Transaction.create(
                                type=Transaction.PaymentType.by_admin,
                                status=Transaction.Status.finished,
                                amount=user[2],
                                amount_paid=user[2],
                                user=dbuser,
                            )
                            await ByAdminPayment.create(
                                by_admin_id=admin.id, transaction=transaction
                            )
                        elif user[2] < 0:
                            await Invoice.create(
                                type=Invoice.Type.by_admin,
                                amount=user[2] * -1,
                                user=dbuser,
                            )
                    await cursor.execute(
                        f"SELECT username FROM invoice WHERE Status='active' AND id_user={dbuser.id}"
                    )
                    proxies = await cursor.fetchall()
                    for proxy in proxies:
                        dbproxy = await Proxy.filter(username=proxy[0])
                        if not dbproxy:
                            dbproxy = await Proxy.create(
                                username=proxy[0], server=server, user=dbuser
                            )
    finally:
        await models.on_shutdown()


if __name__ == "__main__":
    asyncio.run(run())
