from datetime import datetime as dt
from typing import Any, Literal

import httpx
from httpx import Timeout
from pydantic import BaseModel

import config
from app.utils import settings


def get_parsed_query_parameters(data: dict[str, str]) -> str:
    return "&".join(
        [f"{key}={value}" for key, value in data.items() if value is not None]
    )


class TronsellerError(Exception):
    pass


class ResultData(BaseModel):
    Token: str
    FullPaymentUrl: str


class OrderResult(BaseModel):
    IsSuccessful: bool
    Code: int
    Message: str
    Data: ResultData | None = None


class TSWebhookResult(BaseModel):
    UniqueCode: str
    PaymentID: int
    UserTelegramId: int
    Wallet: str
    Hash: str | None = None
    TronAmount: float
    IsPaid: bool
    PaymentDate: dt


class TronadoAPI:
    DEFAULT_HEADERS = {"content-type": "application/json"}

    cached_trx_price: int = None
    last_cached_trx: int = None

    @classmethod
    async def _call_api(
        cls,
        method: Literal["GET", "POST"],
        path: str,
        headers: dict[str, str] = None,
        get_data: dict[str, Any] = None,
        post_data: dict[str, Any] = None,
    ):
        _settings = settings.get_settings().payment_tronado
        if not headers:
            headers = {}
        if not headers.get("x-api-key"):
            if _settings.api_key:
                headers.update(
                    {
                        "x-api-key": _settings.api_key,
                    }
                )
        async with httpx.AsyncClient(headers=headers, timeout=Timeout(10.0)) as client:
            url = _settings.api_base_url.rstrip("/") + "/" + path.lstrip("/")
            if method == "GET":
                if get_data:
                    url = url + "?" + get_parsed_query_parameters(data=get_data)
                r = await client.get(url=url)
                if r.status_code == 200:
                    return r.json()
                else:
                    raise TronsellerError(f"{r.text}")
            elif method == "POST":
                if get_data:
                    url = url + "?" + get_parsed_query_parameters(data=get_data)
                r = await client.post(url=url, json=post_data)
                if r.status_code in {200, 201}:
                    return r.json()
                else:
                    raise TronsellerError(f"{r.text}")

    @classmethod
    async def get_order_token(
        cls,
        payment_id: str,
        tron_amount: float,
        wallet_address: str,
        wage_from_business_percentage: int = 0,
    ) -> OrderResult:
        callback_url = config.WEBHOOK_BASE_URL + "/tronseller"
        data = {
            "PaymentID": payment_id,
            "WalletAddress": wallet_address,
            "TronAmount": tron_amount,
            "CallbackUrl": callback_url,
        }
        get_data = None
        if wage_from_business_percentage:
            get_data = {"wageFromBusinessPercentage": wage_from_business_percentage}
        r = await cls._call_api(
            "POST",
            "/api/GetOrderToken",
            headers={"Content-Type": "application/json"},
            get_data=get_data,
            post_data={k: v for k, v in data.items() if v is not None},
        )
        result = OrderResult.model_validate(r)
        if not result.IsSuccessful:
            raise TronsellerError(f"TronsellerError {result.Code}: {result.Message}")
        return result

    @classmethod
    async def get_order_by_payment_id(
        cls,
        payment_id: str,
    ) -> TSWebhookResult:
        r = await cls._call_api(
            "POST",
            f"/Order/GetStatusByPaymentID/{payment_id}",
            headers={"Content-Type": "application/json"},
        )
        if err := r.get("Error"):
            raise TronsellerError(err)
        return TSWebhookResult.model_validate(r)

    @classmethod
    async def get_tron_price_to_toman(cls, use_cache: bool = True) -> int:
        """Fetch latest trx price

        the price will be cached for 5 minutes
        """
        if use_cache and cls.cached_trx_price:
            if not cls.last_cached_trx or (
                cls.last_cached_trx - dt.now().timestamp() > 5
            ):  # five minute cache
                return await cls.get_price(use_cache=False)
            return cls.cached_trx_price

        r = await cls._call_api("POST", "/Tron/GetPriceToToman")
        if r:
            price = r.get("TronPriceToman")
            cls.cached_trx_price = int(price)
            cls.last_cached_trx = dt.now().timestamp()
            return cls.cached_trx_price
        else:
            raise TronsellerError("could not fetch trx price from api")
