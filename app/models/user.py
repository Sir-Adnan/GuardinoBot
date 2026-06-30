import uuid
from enum import Enum, IntEnum
from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.functions import Sum

from . import TimedBase

if TYPE_CHECKING:
    from .proxy import Proxy
    from .service import Discount, Service, ServiceMenu
    from .setting import Card


class User(TimedBase):
    class Meta:
        table = "users"

    class Role(IntEnum):
        user = 0
        reseller = 1
        admin = 2
        super_user = 3

    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=200, null=True)
    name = fields.CharField(max_length=200, null=True)
    phone_number = fields.CharField(max_length=14, null=True)
    balance = fields.IntField(default=0)
    blocked_bot = fields.BooleanField(default=False)

    total_spent = fields.IntField(default=0)
    is_blocked = fields.BooleanField(default=False)
    is_postpaid = fields.BooleanField(default=False)
    is_verified = fields.BooleanField(default=False)
    card_to_card_auto_accept = fields.BooleanField(default=False)
    max_post_paid_credit = fields.IntField(default=1_000_000)
    gift_given_to_referrer = fields.BooleanField(default=False)

    role = fields.IntEnumField(Role, default=Role.user)
    custom_name = fields.CharField(max_length=64, null=True)

    setting: fields.BackwardOneToOneRelation["UserSetting"]

    force_join_check = fields.DatetimeField(null=True)

    parent: fields.ForeignKeyNullableRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "childs",
        on_delete=fields.SET_NULL,
        null=True,
    )
    referrer: fields.ForeignKeyNullableRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "referred",
        on_delete=fields.SET_NULL,
        null=True,
    )

    referred: fields.ReverseRelation["User"]  # users who are joined by this user
    proxies: fields.ReverseRelation["Proxy"]
    invoices: fields.ReverseRelation["Invoice"]
    transactions: fields.ReverseRelation["Transaction"]
    purchased_services: fields.ManyToManyRelation["Service"]
    used_discounts: fields.ManyToManyRelation["Discount"]
    reserved_discounts: fields.ManyToManyRelation["Discount"]
    service_menues: fields.ManyToManyRelation["ServiceMenu"]
    service_filters: fields.ManyToManyRelation["Service"]

    _m2m_order = (
        "purchased_services",
        "used_discounts",
        "reserved_discounts",
        "service_menues",
        "service_filters",
    )  # << here put your M2M fields names

    async def get_balance(self) -> int:
        # Two independent aggregates (not one combined row): a user with no
        # finished transactions must not raise IndexError, and any invoices
        # still have to be subtracted even when there are zero transactions.
        trx = (
            await self.transactions.filter(status=Transaction.Status.finished)
            .annotate(s=Sum("amount"))
            .values("s")
        )
        inv = (
            await self.invoices.filter(is_draft=False)
            .annotate(s=Sum("amount"))
            .values("s")
        )
        trx_sum = (trx[0].get("s") if trx else 0) or 0
        inv_sum = (inv[0].get("s") if inv else 0) or 0
        return int(trx_sum) - int(inv_sum)

    async def get_available_credit(self, balance: int = None) -> int:
        if balance is None:
            balance = await self.get_balance()
        if self.is_postpaid:
            return balance + self.max_post_paid_credit
        return balance


class UserSetting(TimedBase):
    class Meta:
        table = "user_settings"

    class SortProxyList(str, Enum):
        created_ascending = "created_at"
        created_descending = "-created_at"
        renewed_ascending = "renewed_at"
        renewed_descending = "-renewed_at"
        # expire_ascending = ""
        # expire_descending = ""

    class FilterProxyList(str, Enum):
        all = "all"
        active = "active"
        disabled = "disabled"
        limited = "limited"
        expired = "expired"

    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User",
        "setting",
        on_delete=fields.CASCADE,
        null=False,
        pk=True,
    )
    proxy_username_prefix = fields.CharField(max_length=25, null=True)
    discount_percentage = fields.IntField(default=0)
    daily_test_services = fields.IntField(default=1)

    proxy_list_sort_by = fields.CharEnumField(
        SortProxyList, max_length=20, default=SortProxyList.created_ascending, null=True
    )
    proxy_list_filter_by = fields.CharEnumField(
        FilterProxyList, max_length=20, default=FilterProxyList.all, null=True
    )
    # ...


class InvoiceReminder(TimedBase):
    class Meta:
        table = "invoice_reminders"

    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        "invoice_reminders",
        on_delete=fields.CASCADE,
    )


class Invoice(TimedBase):
    class Meta:
        table = "invoices"

    class Type(IntEnum):
        purchase = 1
        renew_now = 2
        renew_reserve = 3
        parent_charged_child = 4
        by_admin = 5

    id = fields.IntField(pk=True)
    amount = fields.IntField(null=False)
    type = fields.IntEnumField(Type, default=Type.purchase)
    is_paid = fields.BooleanField(default=False)
    is_draft = fields.BooleanField(default=False)
    service: fields.ForeignKeyNullableRelation["Service"] = fields.ForeignKeyField(
        "models.Service",
        "invoices",
        on_delete=fields.SET_NULL,
        null=True,
    )
    proxy: fields.ForeignKeyNullableRelation["Proxy"] = fields.ForeignKeyField(
        "models.Proxy",
        "invoices",
        on_delete=fields.SET_NULL,
        null=True,
    )
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        "invoices",
        on_delete=fields.CASCADE,
    )
    transaction: fields.ForeignKeyNullableRelation["Transaction"] = (
        fields.ForeignKeyField(
            "models.Transaction",
            "invoices",
            on_delete=fields.SET_NULL,
            null=True,
        )
    )


class Transaction(TimedBase):
    class Meta:
        table = "payment_transactions"

    class PaymentType(IntEnum):
        crypto = 1
        card_to_card = 2
        perfectmoney = 3
        rial_gateway = 4
        by_admin = 5
        gift = 6
        tronseller = 7

        # the model should have 'crypto_payment', 'card_to_card_payment' or ... based on the type

    class Status(IntEnum):
        waiting = 1
        failed = 2
        canceled = 3
        partially_paid = 4
        finished = 5
        rejected = 6
        sending = 7
        confirming = 8

    id = fields.BigIntField(pk=True)
    type = fields.IntEnumField(PaymentType, null=False)
    status = fields.IntEnumField(Status, default=Status.waiting)

    finished_at = fields.DatetimeField(null=True)
    amount = fields.IntField(null=False)
    amount_paid = fields.IntField(null=True)
    amount_free_given = fields.IntField(default=0)

    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "transactions",
        on_delete=fields.CASCADE,
        null=False,
    )
    crypto_payment: fields.ReverseRelation["CryptoPayment"]
    perfectmoney_payment: fields.ReverseRelation["PerfectMoneyPayment"]
    card_to_card_payment: fields.ReverseRelation["CardToCardPayment"]
    rialgateway_payment: fields.ReverseRelation["RialGatewayPayment"]
    tronseller_payment: fields.ReverseRelation["TronsellerPayment"]
    byadmin_payment: fields.ReverseRelation["ByAdminPayment"]
    gift_payment: fields.ReverseRelation["GiftPayment"]


class CryptoPayment(TimedBase):
    class Meta:
        table = "payments_crypto"

    class PaymentStatus(IntEnum):
        waiting = 0
        confirming = 1
        confirmed = 2
        sending = 3
        partially_paid = 4
        finished = 5
        failed = 6
        refunded = 7
        expired = 8

    class Provider(str, Enum):
        nowpayments = "nowpayments"
        swapwallet = "swapwallet"
        eswap = "eswap"
        swapino = "swapino"
        plisio = "plisio"  # fits the existing VARCHAR(11) column → no migration
        offline = "offline"  # manual crypto (admin wallet → user TXID/screenshot → approve)

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.crypto
    )
    provider = fields.CharEnumField(
        Provider,
        default=Provider.nowpayments,
    )
    extra_data = fields.JSONField(null=True)

    usdt_rate = fields.IntField()
    invoice_id = fields.CharField(max_length=64, null=True)
    payment_id = fields.CharField(max_length=64, null=True)
    order_id = fields.CharField(max_length=64, null=True)
    price_amount = fields.FloatField()
    price_currency = fields.CharField(max_length=20)
    nowpm_created_at = fields.DatetimeField(null=True)

    pay_currency = fields.CharField(max_length=32, null=True)
    pay_amount = fields.FloatField(null=True)
    order_description = fields.CharField(max_length=64, null=True)
    nowpm_updated_at = fields.DatetimeField(null=True)
    payment_status = fields.IntEnumField(PaymentStatus, default=PaymentStatus.waiting)
    outcome_amount = fields.FloatField(null=True)
    outcome_currency = fields.CharField(max_length=20, null=True)
    purchase_id = fields.CharField(max_length=64, null=True)
    pay_address = fields.CharField(max_length=128, null=True)
    fee = fields.JSONField(null=True)

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "crypto_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class CardToCardPayment(TimedBase):
    class Meta:
        table = "payments_cardtocard"

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.card_to_card
    )
    admin_messages = fields.JSONField(null=True)
    destination_card: fields.ForeignKeyNullableRelation["Card"] = (
        fields.ForeignKeyField(
            "models.Card",
            "payments",
            on_delete=fields.SET_NULL,
            null=True,
        )
    )

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "card_to_card_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class RialGatewayPayment(TimedBase):
    class Meta:
        table = "payments_rialgateway"

    class Provider(str, Enum):
        fastpay = "fastpay"
        swapwallet = "swapwallet"
        payping = "payping"
        aqaye_pardakht = "aqaye_pardakht"
        zibal = "zibal"
        madpal = "madpal"
        zarinpal = "zarinpal"

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.rial_gateway
    )
    provider = fields.CharEnumField(Provider, default=Provider.fastpay)
    data = fields.JSONField()
    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "rialgateway_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class PerfectMoneyPayment(TimedBase):
    class Meta:
        table = "payments_perfectmoney"

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.perfectmoney
    )
    usd_rate = fields.IntField(null=False)
    payee_account = fields.CharField(max_length=64)
    ev_number = fields.CharField(max_length=64)
    ev_code = fields.CharField(max_length=64)
    ev_amount_currency = fields.CharField(max_length=32, null=True)
    payment_batch_number = fields.CharField(max_length=64, null=True)

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "perfectmoney_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class ByAdminPayment(TimedBase):
    class Meta:
        table = "payments_byadmin"

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.by_admin
    )
    by_admin: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        "balance_transactions",
        on_delete=fields.SET_NULL,
        null=True,
    )

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "byadmin_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class GiftPayment(TimedBase):
    class Meta:
        table = "payments_gift"

    class GiftType(IntEnum):
        referral = 1

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.gift
    )
    gift_type = fields.IntEnumField(GiftType, default=GiftType.referral)
    invitee: fields.ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        on_delete=fields.SET_NULL,
        null=True,
    )

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "gift_payment",
        on_delete=fields.CASCADE,
        null=False,
    )


class TronsellerPayment(TimedBase):
    class Meta:
        table = "payments_tronseller"

    class Provider(str, Enum):
        tronseller = "tronseller"
        tronado = "tronado"

    type = fields.IntEnumField(
        Transaction.PaymentType, default=Transaction.PaymentType.tronseller
    )
    provider = fields.CharEnumField(Provider, default=Provider.tronseller)

    unique_code = fields.CharField(max_length=128, null=True)
    wallet = fields.CharField(max_length=128)
    tron_amount = fields.FloatField()
    extra_data = fields.JSONField(null=True)

    trx_rate = fields.IntField()

    transaction: fields.OneToOneRelation[Transaction] = fields.OneToOneField(
        "models.Transaction",
        "tronseller_payment",
        on_delete=fields.CASCADE,
        null=False,
    )
