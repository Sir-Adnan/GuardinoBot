import json
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Literal

import httpx
import zeep
from pydantic import BaseModel, ValidationInfo, model_validator

import config
from app.utils import settings


def get_parsed_query_parameters(data: dict[str, Any]) -> str:
    return urllib.parse.urlencode(
        {key: value for key, value in data.items() if value is not None}
    )


class GatewayError(Exception):
    def __init__(self, *args: object, result: dict[str, Any] = None) -> None:
        self.result = result
        super().__init__(*args)


class GatewayCreateResponse(BaseModel, ABC):
    class Config:
        extra = "allow"
        from_attributes = True

    url: str = ""


class GatewayVerifyResponse(BaseModel, ABC):
    class Config:
        extra = "allow"
        from_attributes = True

    pass


def get_pay_url(url: str, amount: int = None) -> str:
    if config.RIALGATEWAY_REWRITE_CALLBACK_URL:
        return (
            config.RIALGATEWAY_REWRITE_CALLBACK_URL.rstrip("/")
            + "/topay/?"
            + get_parsed_query_parameters({"pay_url": url, "amount": amount})
        )
    return url


def get_callback_url(provider: str, extras: dict[str, Any] | None = None) -> str:
    if config.RIALGATEWAY_REWRITE_CALLBACK_URL:
        url = config.RIALGATEWAY_REWRITE_CALLBACK_URL.rstrip("/") + "/frompay/"
    else:
        url = config.WEBHOOK_BASE_URL + "/" + provider
    if not extras:
        return url
    return url + "?" + get_parsed_query_parameters(extras)


class PaypingCreateResponse(GatewayCreateResponse):
    code: str

    @model_validator(mode="before")
    @classmethod
    def _add_url_from_trx_id(cls, data: Any, info: ValidationInfo) -> Any:
        if not isinstance(data, dict):
            return data
        if (trx_id := data.get("code", None)) is not None:
            data["url"] = get_pay_url(
                f"https://api.payping.ir/v2/pay/gotoipg/{trx_id}",
                amount=info.context.get("amount", None) if info.context else None,
            )
        return data


class PaypingVerifyResponse(GatewayVerifyResponse):
    amount: int
    cardNumber: str
    cardHashPan: str = None


class AqayePardakhtCreateResponse(GatewayCreateResponse):
    status: str
    transid: str
    code: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _add_url_from_trx_id(cls, data: Any, info: ValidationInfo) -> Any:
        if not isinstance(data, dict):
            return data
        if (trx_id := data.get("transid", None)) is not None:
            data["url"] = get_pay_url(
                f"https://panel.aqayepardakht.ir/startpay/{trx_id}",
                amount=info.context.get("amount", None) if info.context else None,
            )

        return data


class AqayePardakhtVerifyResponse(GatewayVerifyResponse):
    status: str
    code: int


class ZibalCreateResponse(GatewayCreateResponse):
    trackId: str | int
    result: int
    message: str

    @model_validator(mode="before")
    @classmethod
    def _add_url_from_trx_id(cls, data: Any, info: ValidationInfo) -> Any:
        if not isinstance(data, dict):
            return data
        if (trx_id := data.get("trackId", None)) is not None:
            data["url"] = get_pay_url(
                f"https://gateway.zibal.ir/start/{trx_id}",
                amount=info.context.get("amount", None) if info.context else None,
            )
        return data


class ZibalVerifyResponse(GatewayVerifyResponse):
    paidAt: str | None = None
    cardNumber: str | None = None
    status: int | None = None
    amount: int | None = None
    refNumber: str | None = None
    description: str | None = None
    orderId: int | None = None
    result: int
    message: str


class ZarinpalCreateResponse(GatewayCreateResponse):
    code: int
    message: str
    authority: str
    fee_type: str
    fee: int

    @model_validator(mode="before")
    @classmethod
    def _add_url_from_Authority(cls, data: Any, info: ValidationInfo) -> Any:
        if not isinstance(data, dict):
            return data
        if (authority := data.get("authority", None)) is not None:
            data["url"] = get_pay_url(
                f"https://www.zarinpal.com/pg/StartPay/{authority}",
                amount=info.context.get("amount", None) if info.context else None,
            )
        return data


class ZarinpalVerifyResponse(GatewayVerifyResponse):
    code: int
    authority: str
    ref_id: int
    card_pan: str | None = None
    card_hash: str | None = None
    fee_type: str
    fee: int


class BaseRialGateway(ABC):
    """Base abstract class for rial-gateway payments"""

    @classmethod
    async def _call_api(
        cls,
        method: Literal["GET", "POST"],
        path: str,
        base_url: str,
        headers: dict[str, str] = None,
        query_data: dict[str, Any] = None,
        json_data: dict[str, Any] = None,
        form_data: dict[str, Any] = None,
        timeout: httpx.Timeout | None = None,
    ):
        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout if timeout is not None else httpx.Timeout(15),
        ) as client:
            url = base_url.rstrip("/") + "/" + path.lstrip("/")
            if query_data:
                url = url + "?" + get_parsed_query_parameters(data=query_data)
            if method == "GET":
                r = await client.get(url=url)
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    data = None
                if r.status_code == 200:
                    return data
                else:
                    raise GatewayError(
                        f"{cls.__name__} {r.status_code}: {r.text}",
                        result=dict(status_code=r.status_code, **data if data else {}),
                    )
            elif method == "POST":
                r = await client.post(url=url, json=json_data, data=form_data)
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    data = None
                if r.status_code in {200, 201}:
                    return data
                else:
                    raise GatewayError(
                        f"{cls.__name__} {r.status_code}: {r.text}",
                        result=dict(status_code=r.status_code, **data if data else {}),
                    )

    @classmethod
    @abstractmethod
    async def create(
        cls, amount: int, transaction_id: int, callback_url: str, *args, **kwargs
    ) -> GatewayCreateResponse:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def verify(
        cls, amount: int, ref_id: str | int, *args, **kwargs
    ) -> GatewayVerifyResponse:
        raise NotImplementedError


class PaypingAPI(BaseRialGateway):
    BASE_URL = config.PAYPING_API_URL

    @classmethod
    async def create(
        cls,
        amount: int,
        transaction_id: int,
        payer_name: str | None = None,
        description: str | None = None,
    ) -> PaypingCreateResponse:
        _settings = settings.get_settings().payment_payping
        data = {
            "amount": amount,
            "clientRefId": transaction_id,
            "payerName": payer_name,
            "description": description,
            "returnUrl": get_callback_url("payping"),
        }
        r = await cls._call_api(
            "POST",
            "/pay",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_settings.api_key}",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        return PaypingCreateResponse.model_validate(r, context={"amount": amount})

    @classmethod
    async def verify(cls, amount: int, ref_id: str | int) -> PaypingVerifyResponse:
        _settings = settings.get_settings().payment_payping
        data = {
            "amount": amount,
            "refid": ref_id,
        }
        r = await cls._call_api(
            "POST",
            "/pay/verify",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_settings.api_key}",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        return PaypingVerifyResponse.model_validate(r)


class AqayePardakhtAPI(BaseRialGateway):
    BASE_URL = config.AQAYEPARDAKHT_API_URL

    @classmethod
    async def create(
        cls,
        amount: int,
        transaction_id: int,
        description: str | None = None,
    ) -> AqayePardakhtCreateResponse:
        _settings = settings.get_settings().payment_aqaye_pardakht
        data = {
            "pin": _settings.api_key,
            "amount": amount,
            "invoice_id": transaction_id,
            "callback": get_callback_url("aqaye_pardakht"),
            "description": description,
        }
        r = await cls._call_api(
            "POST",
            "/api/v2/create",
            cls.BASE_URL,
            form_data={k: v for k, v in data.items() if v is not None},
            timeout=httpx.Timeout(25),
        )
        return AqayePardakhtCreateResponse.model_validate(r, context={"amount": amount})

    @classmethod
    async def verify(
        cls, amount: int, ref_id: str | int
    ) -> AqayePardakhtVerifyResponse:
        _settings = settings.get_settings().payment_aqaye_pardakht

        data = {
            "pin": _settings.api_key,
            "amount": amount,
            "transid": ref_id,
        }
        r = await cls._call_api(
            "POST",
            "/api/v2/verify",
            cls.BASE_URL,
            form_data={k: v for k, v in data.items() if v is not None},
            timeout=httpx.Timeout(25),
        )
        result = AqayePardakhtVerifyResponse.model_validate(r)
        if result.status == "success":
            return result
        raise GatewayError(
            f"{cls.__name__}: Error Verifying Transaction!", result=result.model_dump()
        )


class ZibalAPI(BaseRialGateway):
    BASE_URL = config.ZIBAL_API_URL

    @classmethod
    async def create(
        cls,
        amount: int,
        transaction_id: int,
        description: str | None = None,
    ) -> ZibalCreateResponse:
        _settings = settings.get_settings().payment_zibal
        data = {
            "merchant": _settings.api_key,
            "amount": amount * 10,  # convert amount to rial
            "orderId": transaction_id,
            "description": description,
            "callbackUrl": get_callback_url("zibal"),
        }
        r = await cls._call_api(
            "POST",
            "/request",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        if (result := r.get("result")) != 100:
            raise GatewayError(f"Error creating payment! {result}: {r.get('message')}")
        return ZibalCreateResponse.model_validate(r, context={"amount": amount})

    @classmethod
    async def verify(cls, amount: int, ref_id: str | int) -> ZibalVerifyResponse:
        _settings = settings.get_settings().payment_zibal
        data = {
            "merchant": _settings.api_key,
            "trackId": ref_id,
        }
        r = await cls._call_api(
            "POST",
            "/verify",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        if (result := r.get("result")) not in [100, 201]:
            raise GatewayError(
                f"Error verifying payment! {result}: {r.get('message')}",
                result={"result": result},
            )
        return ZibalVerifyResponse.model_validate(r)


class ZarinpalAPI(BaseRialGateway):
    BASE_URL = config.ZARINPAL_BASE_URL

    @classmethod
    async def create(
        cls,
        amount: int,
        transaction_id: int,
        description: str | None = None,
    ) -> ZarinpalCreateResponse:
        _settings = settings.get_settings().payment_zarinpal
        data = {
            "merchant_id": _settings.api_key,
            "amount": amount,
            "currency": "IRT",
            "description": description,
            "callback_url": get_callback_url(
                "zarinpal", {"order_id": transaction_id}
            ),  # zarinpal is not sending order_id in 'metadata' in the callback_url for some reason
            "metadata": {"order_id": str(transaction_id)},
        }
        r = await cls._call_api(
            "POST",
            "/payment/request.json",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        if errors := r.get("errors"):
            raise GatewayError(
                f"Error creating payment! {errors.get('code')}: {errors.get('message')}"
            )
        return ZarinpalCreateResponse.model_validate(
            r.get("data"), context={"amount": amount}
        )

    @classmethod
    async def verify(cls, amount: int, ref_id: str | int) -> ZarinpalVerifyResponse:
        _settings = settings.get_settings().payment_zarinpal
        data = {
            "merchant_id": _settings.api_key,
            "amount": amount,
            "authority": ref_id,
        }
        r = await cls._call_api(
            "POST",
            "/payment/verify.json",
            cls.BASE_URL,
            headers={
                "Content-Type": "application/json",
            },
            json_data={k: v for k, v in data.items() if v is not None},
        )
        if errors := r.get("errors"):
            raise GatewayError(
                f"Error verifying payment! {errors.get('code')}: {errors.get('message')}"
            )
        data = r.get("data")
        data["authority"] = ref_id
        return ZarinpalVerifyResponse.model_validate(data)
