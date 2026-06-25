import random
import string
from datetime import datetime as dt
from enum import Enum
from typing import TYPE_CHECKING, Literal, Type

from tortoise import fields
from tortoise.expressions import F, Q, RawSQL
from tortoise.signals import post_save
from tortoise.validators import MinValueValidator

from app.models import TimedBase
from app.panels import get_panel

if TYPE_CHECKING:
    from .proxy import Proxy
    from .server import Server
    from .user import User


class ServiceMenu(TimedBase):
    class Meta:
        table = "service_menues"

    id = fields.IntField(pk=True)

    title = fields.CharField(max_length=64, null=False, unique=True)
    description = fields.TextField(null=True)  # raw html description

    # display options: services and sub-menues will obey this settings
    purchase = fields.BooleanField(default=True)
    renew = fields.BooleanField(default=True)

    resellers_only = fields.BooleanField(default=False)
    users_only = fields.BooleanField(default=False)

    users: fields.ManyToManyRelation["User"] = fields.ManyToManyField(
        "models.User",
        through="user_to_service_menues",
        related_name="service_menues",
    )

    parent: fields.ForeignKeyNullableRelation["ServiceMenu"] = fields.ForeignKeyField(
        "models.ServiceMenu",
        "childs",
        on_delete=fields.CASCADE,
        null=True,
    )
    services: fields.ManyToManyRelation["Service"] = fields.ManyToManyField(
        "models.Service",
        through="services_to_menues",
        related_name="menues",
    )


class Service(TimedBase):
    class Meta:
        table = "services"
        ordering = ["priority", "id"]

    class ServiceProxyFlow(str, Enum):
        none = None
        xtls_rprx_vision = "xtls-rprx-vision"

    class UsageResetStrategy(str, Enum):
        no_reset = "no_reset"
        day = "day"
        week = "week"
        month = "month"
        year = "year"

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=64, null=False)
    data_limit = fields.BigIntField(null=False)  # in bytes
    expire_duration = fields.BigIntField(null=False)  # in seconds
    all_inbounds = fields.BooleanField(default=False)
    inbounds = fields.JSONField(null=False)  # Marzban: {protocol: [tags]}
    flow = fields.CharEnumField(
        ServiceProxyFlow, max_length=20, null=True, default=ServiceProxyFlow.none
    )
    # Panel-specific provisioning that does not fit Marzban's inbounds/flow.
    # PasarGuard: {"group_ids": [int], "proxy_settings": {...optional...}}.
    # Guardino (phase 2): {"node_ids": [int], "pricing_mode": "...", ...}.
    panel_config = fields.JSONField(null=True)
    price = fields.IntField(null=False, validators=[MinValueValidator(0)])  # in Tomans

    one_time_only = fields.BooleanField(
        default=False
    )  # each user can only buy this once
    is_test_service = fields.BooleanField(
        default=False,  # normal users can get it only once, resellers can get it for config.DEFAULT_DAILY_TEST_SERVICES or user.setting.daily_test_services
    )
    priority = fields.IntField(
        default=1_000_000
    )  # a large number so the row goes to the end of the list, a re-index is triggered after insertion

    purchaseable = fields.BooleanField(default=True)
    renewable = fields.BooleanField(default=True)

    resellers_only = fields.BooleanField(default=False)
    users_only = fields.BooleanField(default=False)
    user_filter = fields.BooleanField(default=False)

    user_filters: fields.ManyToManyRelation["User"] = fields.ManyToManyField(
        "models.User",
        through="services_users_filters",
        related_name="service_filters",
    )

    create_on_hold_users = fields.BooleanField(default=False)
    usage_reset_strategy = fields.CharEnumField(
        UsageResetStrategy, default=UsageResetStrategy.no_reset
    )
    append_available_data_renew = fields.BooleanField(default=False)

    server: fields.ForeignKeyRelation["Server"] = fields.ForeignKeyField(
        "models.Server",
        "services",
        on_delete=fields.CASCADE,
        null=False,
    )

    purchased_by: fields.ManyToManyRelation["User"] = fields.ManyToManyField(
        "models.User",
        through="user_purchased",
        related_name="purchased_services",
    )
    menues: fields.ManyToManyRelation["ServiceMenu"]

    discounts: fields.ManyToManyRelation["Discount"]

    _m2m_order = (
        "purchased_by",
        "discounts",
        "menues",
        "user_filters",
    )  # DO NOT CHANGE THE ORDER if you don't know what you're doing

    @property
    def display_name(self):
        if not self.price:
            return self.name
        return f"{self.name} | {self.price:,} تومان"

    async def change_priority(self, direction: Literal[1, -1] = 1) -> None:
        _priority = self.priority
        if direction == 1:
            ref = await Service.filter(priority__gt=_priority).first()
        else:
            ref = (
                await Service.filter(priority__lt=_priority)
                .order_by("-priority")
                .first()
            )  # reverse ordering
        if not ref:
            raise ValueError(
                f"Can not change proirity because there is no element in {direction} direction"
            )

        self.priority = ref.priority
        ref.priority = _priority
        await Service.bulk_update([self, ref], fields=["priority"])

    async def get_discount(
        self, user: "User", type: Literal["purchase", "renew"] = "purchase"
    ) -> "Discount":
        q = Discount.filter(
            Q(is_active=True),
            Q(expires_at__isnull=True) | Q(expires_at__gt=dt.utcnow()),
            Q(services__id=self.id)
            | Q(
                id__not_in=RawSQL("(SELECT `discounts_id` FROM `service_discounts`)"),
            ),
            Q(code__isnull=True) | Q(reserved_by_users__id=user.id),
            Q(use_counts__isnull=True)
            | Q(use_counts=0)
            | Q(used_times__lt=F("use_counts")),
            Q(once_per_user=False) | ~Q(used_by__id=user.id),
        )
        if type == "purchase":
            q = q.filter(on_purchase=True)
        elif type == "renew":
            q = q.filter(on_renew=True)
        return await q.first()

    async def get_display_name(
        self, user: "User", type: Literal["purchase", "renew"] = "purchase"
    ) -> str:
        if not self.price:
            return self.name

        discount = await self.get_discount(user=user, type=type)
        if not discount:
            return f"{self.name} | {self.price:,} تومان"
        return f"{self.name} |[🔥 -{discount.percentage}%] {self.price - int(self.price * (discount.percentage / 100)):,} تومان"

    async def get_price(
        self, discount_percent: int = None, discount: "Discount" = None
    ) -> int:
        if self.price == 0:
            return self.price
        if discount_percent:
            return self.price - int(self.price * (discount_percent / 100))

        if discount:
            return self.price - int(self.price * (discount.percentage / 100))
        return self.price

    def create_proxy_protocols(self, protocol: str) -> dict[str, str]:
        if protocol == "vless" and self.flow != self.ServiceProxyFlow.none:
            return {"flow": self.flow}
        return {}

    async def get_inbounds(self) -> dict:
        """Provisioning catalog for this service's server.

        Marzban: {protocol: [tags]}. PasarGuard: {"groups": [...], "inbounds": [...]}.
        When all_inbounds is False, returns the stored Marzban-style inbounds.
        """
        if self.all_inbounds:
            return await get_panel(self.server_id).get_inbounds()
        return self.inbounds


async def re_index_service_priorities() -> None:
    objs = await Service.all()
    if objs:
        for i, obj in enumerate(objs, start=0):
            obj.priority = i
        await Service.bulk_update(objs, fields=["priority"])


@post_save(Service)
async def re_index_priorities(
    sender: Type[Service],
    instance: Service,
    created: bool,
    *_,
) -> None:
    if created:
        await re_index_service_priorities()


class Discount(TimedBase):
    class Meta:
        table = "discounts"

    id = fields.IntField(pk=True)
    is_active = fields.BooleanField(default=True)

    percentage = fields.IntField()

    on_purchase = fields.BooleanField(default=True)
    on_renew = fields.BooleanField(default=False)

    once_per_user = fields.BooleanField(default=False)
    used_times = fields.IntField(default=0)
    use_counts = fields.IntField(null=True, default=None)

    code = fields.CharField(max_length=32, null=True, unique=True)

    @classmethod
    def generate_code(cls, min_length: int = 8, max_length: int = 16) -> str:
        return "".join(
            random.choices(string.ascii_letters + string.digits, k=max_length)[
                : random.randint(min_length, max_length)
            ]
        )

    expires_at = fields.DatetimeField(null=True)

    services: fields.ManyToManyRelation["Service"] = fields.ManyToManyField(
        "models.Service",
        through="service_discounts",
        related_name="discounts",
    )
    purchased_proxies: fields.ManyToManyRelation["Proxy"] = fields.ManyToManyField(
        "models.Proxy",
        through="proxy_discounts",
        related_name="given_dscounts",
    )

    used_by: fields.ManyToManyRelation["User"] = fields.ManyToManyField(
        "models.User",
        through="user_discounts",
        related_name="used_discounts",
    )
    reserved_by_users: fields.ManyToManyRelation["User"] = fields.ManyToManyField(
        "models.User",
        through="user_reserved_discount",
        related_name="reserved_discounts",
    )

    @classmethod  # workaround for bug in aerich migrations: https://github.com/tortoise/aerich/issues/150#issuecomment-1076739667
    def describe(cls, serializable: bool = True) -> dict:
        result = super().describe(serializable)
        m2m_order = (
            "services",
            "purchased_proxies",
            "used_by",
            "reserved_by_users",
        )  # << here put your M2M fields names
        assert set(m2m_order) == set(cls._meta.m2m_fields)
        result["m2m_fields"] = [
            cls._meta.fields_map[name].describe(serializable) for name in m2m_order
        ]
        return result
