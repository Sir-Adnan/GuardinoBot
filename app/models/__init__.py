from aiogram import Dispatcher
from tortoise import Tortoise
from tortoise.fields import DatetimeField
from tortoise.models import Model

import config

db = Tortoise()


class Base(Model):
    class Meta:
        abstract = True

    _m2m_order: tuple[str] = ()

    @classmethod  # workaround for bug in aerich migrations: https://github.com/tortoise/aerich/issues/150#issuecomment-1076739667
    def describe(cls, serializable: bool = True) -> dict:
        result = super().describe(serializable)
        if not cls._m2m_order:
            return result
        assert set(cls._m2m_order) == set(cls._meta.m2m_fields)
        result["m2m_fields"] = [
            cls._meta.fields_map[name].describe(serializable) for name in cls._m2m_order
        ]
        return result


class TimedBase(Base):
    class Meta:
        abstract = True

    created_at = DatetimeField(null=True, auto_now_add=True)
    updated_at = DatetimeField(null=True, auto_now=True)


class CreatedTimeBase(Base):
    class Meta:
        abstract = True

    created_at = DatetimeField(null=True, auto_now_add=True)


class SingletonBase(CreatedTimeBase):
    class Meta:
        abstract = True

    @classmethod
    async def get(cls, **kwargs) -> "SingletonBase":
        obj = await cls.first()
        if obj is None:
            obj = await cls.create(**kwargs)
        return obj


async def on_startup():
    await db.init(config=config.TORTOISE_ORM)

    from .service import re_index_service_priorities

    await re_index_service_priorities()


async def on_shutdown():
    await db.close_connections()


def setup_database(dp: Dispatcher):
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
