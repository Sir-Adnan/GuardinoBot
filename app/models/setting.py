import json
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from random import randint
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from tortoise import fields

from app.utils.values import TextValue

from . import TimedBase


class Card(TimedBase):
    class Meta:
        table = "cards"

    id = fields.IntField(pk=True)
    card_number = fields.CharField(max_length=16)
    card_holder = fields.CharField(max_length=128)
    is_active = fields.BooleanField(default=True)

    @classmethod
    async def get_random(cls) -> "Card":
        count = await cls.filter(is_active=True).count()
        if count:
            return (await cls.filter(is_active=True).all())[randint(0, count - 1)]


class KeyValueBase(TimedBase):
    class Meta:
        abstract = True

    _key = fields.CharField(max_length=128, null=False, pk=True)
    _value = fields.TextField(null=True)

    @classmethod
    def _convert(cls, value: Any) -> Any:
        if isinstance(value, (bool, str, int, float, type(None))):
            return value
        else:
            return json.dumps(value)

    @classmethod
    def _encode_value(self, key: str, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, UUID):
            return value.hex
        if isinstance(value, bool):
            return str(int(value))
        if isinstance(value, (int, str, float, Decimal, Fraction)):
            return str(value)
        if isinstance(value, (list, dict, tuple, set)):
            return json.dumps(value)
        if isinstance(value, TextValue):
            return value.value
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        raise ValueError(
            f"Attribute {key}={value!r} of type {type(value).__name__!r}"
            f" can not be serialized to 'str' for KeyValueBase"
        )

    @classmethod
    async def get_or_create(cls, default: dict[str, Any]) -> dict[str, str]:
        out = dict()
        for k, v in default.items():
            obj, _ = await super().get_or_create(
                {"_value": cls._encode_value(k, v)}, _key=k
            )
            out[k] = obj._value

        # delete the rows not present in defaults
        await cls.filter(_key__not_in=list(default.keys())).all().delete()
        return out

    @classmethod
    async def update(cls, **kwargs: dict[str, Any]) -> None:
        for k, v in kwargs.items():
            await cls.filter(_key=k).update(_value=cls._encode_value(k, v))


class BotSetting(KeyValueBase):
    class Meta:
        table = "bot_settings"


class BotText(KeyValueBase):
    class Meta:
        table = "bot_texts"
