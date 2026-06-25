from enum import Enum
from typing import TYPE_CHECKING, Type

from tortoise import BaseDBAsyncClient, fields
from tortoise.expressions import F
from tortoise.signals import post_save

from . import TimedBase
from .server import Server

if TYPE_CHECKING:
    from .service import Service
    from .user import Invoice, User


class ProxyStatus(Enum):
    active = "active"
    disabled = "disabled"
    limited = "limited"
    expired = "expired"
    on_hold = "on_hold"


class Proxy(TimedBase):
    class Meta:
        table = "proxies"

    id = fields.IntField(pk=True)
    custom_name = fields.CharField(max_length=64, null=True)
    username = fields.CharField(max_length=32, null=False, index=True, unique=True)
    cost = fields.IntField(null=True)
    status = fields.CharEnumField(
        ProxyStatus, max_length=12, default=ProxyStatus.active
    )
    renewed_at = fields.DatetimeField(null=True)

    # Per-alert dedup flags for the proxy_alerts job, e.g.
    # {"expiry": true, "low_data": true, "unused": true, "ended": true}.
    # Self-healing: the job drops a flag once its condition no longer holds
    # (after renew / add-traffic), so a recovered subscription can alert again.
    notified = fields.JSONField(null=True)

    # id-based panels (Guardino hub): remote integer user id + master sub token.
    # Null for username-based panels (Marzban / PasarGuard).
    panel_user_id = fields.BigIntField(null=True)
    sub_token = fields.CharField(max_length=128, null=True)

    service: fields.ForeignKeyNullableRelation["Service"] = fields.ForeignKeyField(
        "models.Service",
        "proxies",
        on_delete=fields.SET_NULL,
        null=True,
    )
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "proxies",
        on_delete=fields.CASCADE,
        null=False,
    )
    server: fields.ForeignKeyRelation["Server"] = fields.ForeignKeyField(
        "models.Server",
        "proxies",
        on_delete=fields.CASCADE,
        null=False,
    )
    reserve: fields.OneToOneNullableRelation["Reserve"]

    @property
    def display_name(self):
        if self.custom_name:
            return f"{self.username} ({self.custom_name})"

        if self.service:
            return f"{self.service.name} ({self.username})"
        return f"({self.username})"


@post_save(Proxy)
async def signal_post_save(
    sender: Type[Proxy],
    instance: Proxy,
    created: bool,
    using_db: BaseDBAsyncClient | None,
    update_fields: list[str],
) -> None:
    if created:
        await Server.filter(id=instance.server_id).update(
            total_proxies=F("total_proxies") + 1
        )


class Reserve(TimedBase):
    class Meta:
        table = "reserves"

    activate_at = fields.DatetimeField(null=True)

    invoice: fields.ForeignKeyRelation["Invoice"] = fields.ForeignKeyField(
        "models.Invoice",
        on_delete=fields.CASCADE,
    )
    proxy: fields.OneToOneRelation["Proxy"] = fields.OneToOneField(
        "models.Proxy",
        "reserve",
        on_delete=fields.CASCADE,
        pk=True,
    )
    service: fields.ForeignKeyRelation["Service"] = fields.ForeignKeyField(
        "models.Service",
        "reserves",
        on_delete=fields.RESTRICT,  # TODO: resolve reserves before deleting service
        null=False,
    )
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "reserves",
        on_delete=fields.CASCADE,
        null=False,
    )


class PurchaseLog(TimedBase):
    class Meta:
        table = "purchase_logs"

    class Type(str, Enum):
        purchase = "purchase"
        renew = "renew"
        reserve = "reserve"

    type = fields.CharEnumField(
        Type,
        default=Type.purchase,
    )
    amount = fields.FloatField(default=0)
    data = fields.BigIntField(null=True)
    proxy: fields.ForeignKeyNullableRelation["Proxy"] = fields.ForeignKeyField(
        "models.Proxy",
        "purchase_logs",
        on_delete=fields.SET_NULL,
        null=True,
    )
    reserve: fields.ForeignKeyNullableRelation["Reserve"] = fields.ForeignKeyField(
        "models.Reserve",
        "purchase_logs",
        on_delete=fields.SET_NULL,
        null=True,
    )
    service: fields.ForeignKeyNullableRelation["Service"] = fields.ForeignKeyField(
        "models.Service",
        "purchase_logs",
        on_delete=fields.SET_NULL,
        null=True,
    )
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "purchase_logs",
        on_delete=fields.SET_NULL,
        null=True,
    )
