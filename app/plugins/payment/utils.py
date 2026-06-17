from typing import Any

from pydantic import BaseModel, model_validator


class Base(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _load_json(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, str):
            return cls.model_validate_json(data)
        return data


class BaseSettings(Base):
    class Config:
        from_attributes = True
        coerce_numbers_to_str = True

    enabled: bool = False
    min_pay_amount: int = 0
    free_after: int = 0
    free_after_percent: int = 0
    is_voucher: bool = False


class BaseTexts(Base):
    class Config:
        from_attributes = True
