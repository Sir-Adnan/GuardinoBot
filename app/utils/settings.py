from enum import Enum
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_core import to_jsonable_python

import config
from app.models import user
from app.models.setting import BotSetting
from app.plugins.payment.card_to_card import card_to_card
from app.plugins.payment.crypto import nowpayments, swapino
from app.plugins.payment.perfect_money import perfect_money
from app.plugins.payment.rial_gateway import (
    aqaye_pardakht,
    auto_select,
    payping,
    zarinpal,
    zibal,
)
from app.plugins.payment.tronseller import tronado

list_of_int_adapter = TypeAdapter(list[int])
dict_of_str_str_adapter = TypeAdapter(dict[str, str])


class UsernameGenerators(str, Enum):
    randomized = "randomized"
    incremental = "incremental"


class Settings(BaseModel):
    """A wrapper around BotSettings database model

    **all nested fields including lists, dictionaries and tuples must have a validator to validate them from json serialized strings.
    """

    @classmethod
    def discover_payment_plugins(cls) -> dict[str, str]:
        return {
            v.default._name: k
            for k, v in cls.model_fields.items()
            if k.startswith("payment_")
        }

    @classmethod
    def payment_plugins(cls) -> dict[str, str]:
        if cls._payment_plugins:
            return cls._payment_plugins
        cls._payment_plugins = cls.discover_payment_plugins()
        return cls._payment_plugins

    _payment_plugins: ClassVar[dict[str, str] | None] = None

    class Config:
        from_attributes = True

    username_generator: UsernameGenerators = UsernameGenerators.randomized

    access_only: bool = False
    referral_system: bool = True

    reset_password_button: bool = True
    show_connect_links_button: bool = True
    show_test_service_in_menu: bool = True
    disable_users_role: user.User.Role = user.User.Role.reseller

    phone_number_verify: bool = False

    delete_expired_users_after_days: int = 0

    remind_invoices_each_n_days: int = 3
    remind_invoices_after_amount: int = 1_000_000

    charge_amount_list: list[int] = config.DEFAULT_CHARGE_AMOUNT_LIST
    charge_amount_orders: list[int] = config.DEFAULT_CHARGE_ORDERS

    default_username_prefix: str = config.DEFAULT_USERNAME_PREFIX

    default_daily_test_services: int = config.DEFAULT_DAILY_TEST_SERVICES
    on_hold_timeout_seconds: int = 259200  # 3 days

    transaction_logs: str | int | None = config.TRANSACTION_LOGS
    orders_logs: str | int | None = config.ORDERS_LOGS

    referral_discount_percent: int = 20

    cancel_payback_fee: int = 10000
    cancel_payback_days: int = 5

    # Guardino reseller-wallet low-balance alert thresholds (toman)
    guardino_balance_warn: int = 1_000_000
    guardino_balance_critical: int = 500_000

    marzban_webhook_secret: str | None = None
    force_join_chats: dict[str, str] | None = config.FORCE_JOIN_CHATS

    # Web-panel button customisation: main-menu key -> custom label (empty/missing
    # key falls back to the hard-coded default in app/utils/buttons.py).
    button_labels: dict[str, str] = {}

    # --- User notification / proxy-alert system (jobs/proxy_alerts.py) ---
    alerts_enabled: bool = True  # master switch
    notify_expiry_enabled: bool = True
    notify_expiry_days: int = 3  # alert when 0 < days_left <= this
    notify_low_data_enabled: bool = True
    notify_traffic_percent: int = 85  # alert when used >= this % of data_limit
    notify_data_remaining_gb: int = 1  # ...or remaining data <= this many GB
    notify_unused_enabled: bool = True
    notify_unused_days: int = 3  # bought & never connected after this many days
    notify_ended_enabled: bool = True  # expired / data-finished

    # payment auto_select
    payment_auto_select: auto_select.Settings = auto_select.Settings()

    # payment crypto
    payment_nowpayments: nowpayments.Settings = nowpayments.Settings()
    payment_swapino: swapino.Settings = swapino.Settings()

    payment_card_to_card: card_to_card.Settings = card_to_card.Settings()
    payment_perfect_money: perfect_money.Settings = perfect_money.Settings()

    # payment rial gateway
    payment_payping: payping.Settings = payping.Settings()
    payment_aqaye_pardakht: aqaye_pardakht.Settings = aqaye_pardakht.Settings()
    payment_zibal: zibal.Settings = zibal.Settings()
    payment_zarinpal: zarinpal.Settings = zarinpal.Settings()

    # payment tronseller
    payment_tronado: tronado.Settings = tronado.Settings()

    @field_validator("charge_amount_list", mode="before")
    def _validate_ch_amlist(cls, v: Any, info: ValidationInfo) -> list[int]:
        if v is None:
            return config.DEFAULT_CHARGE_AMOUNT_LIST

        if isinstance(v, str):
            try:
                return list_of_int_adapter.validate_json(v)
            except ValidationError:
                return []
        return v

    @field_validator("charge_amount_orders", mode="before")
    def _validate_ch_orlist(cls, v: Any, info: ValidationInfo) -> list[int]:
        if v is None:
            return config.DEFAULT_CHARGE_ORDERS
        if isinstance(v, str):
            try:
                return list_of_int_adapter.validate_json(v)
            except ValidationError:
                return []
        return v

    @field_validator("force_join_chats", mode="before")
    def _validate_fjc(cls, v: Any, info: ValidationInfo) -> dict[str, str]:
        if isinstance(v, str):
            try:
                return dict_of_str_str_adapter.validate_json(v)
            except ValidationError:
                return {}
        return v

    @field_validator("button_labels", mode="before")
    def _validate_button_labels(cls, v: Any, info: ValidationInfo) -> dict[str, str]:
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return dict_of_str_str_adapter.validate_json(v)
            except ValidationError:
                return {}
        return v

    @classmethod
    async def from_db(cls) -> "Settings":
        default = {
            key: to_jsonable_python(val.default)
            for key, val in cls.model_fields.items()
        }
        settings = await BotSetting.get_or_create(default=default)
        return cls.model_validate(settings)

    @classmethod
    async def update(cls, **kwargs: dict[str, Any]):
        # validate new values based on model type annotations
        serialized = dict()
        for k, v in kwargs.items():
            cls.__pydantic_validator__.validate_assignment(cls.model_construct(), k, v)
            serialized[k] = to_jsonable_python(
                v
            )  # serialize to json (best option for saving char in db)
        return await BotSetting.update(**serialized)


_settings = Settings()


def get_settings() -> Settings:
    return _settings


async def reload_settings() -> None:
    global _settings
    _settings = await Settings.from_db()
