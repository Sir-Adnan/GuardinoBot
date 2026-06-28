from datetime import datetime as dt
from decimal import Decimal
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


class NowPaymentsError(Exception):
    pass


class MinAmountResponse(BaseModel):
    currency_from: str
    currency_to: str
    min_amount: float
    fiat_equivalent: float


class PaymentResponse(BaseModel):
    payment_id: int | str
    invoice_id: int | str | None = None
    payment_status: str
    pay_address: str | None = None
    price_amount: float | str
    price_currency: str
    pay_amount: float | str | None = None
    pay_currency: str
    order_id: int | str | None = None
    order_description: str | None = None
    created_at: dt | None = None
    updated_at: dt | None = None
    purchase_id: int | str | None = None
    amount_received: float | str | None = None
    actually_paid: float | str | None = None
    network: str | None = None
    network_percision: int | None = None
    network_precision: int | None = None
    expiration_estimate_date: dt | None = None
    outcome_amount: float | str | None = None
    outcome_currency: str | None = None
    fee: dict | None = None
    payin_hash: str | None = None
    payout_hash: str | None = None


class CreateInvoiceResponse(BaseModel):
    id: str
    order_id: str
    order_description: str | None = None
    price_amount: float | str
    price_currency: str
    pay_currency: str | None = None
    ipn_callback_url: str
    invoice_url: str
    success_url: str | None = None
    cancel_url: str | None = None
    created_at: dt
    updated_at: dt


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


class NowPaymentsAPI:
    BASE_URL = config.NP_API_URL

    @classmethod
    async def _call_api(
        cls,
        method: Literal["GET", "POST"],
        path: str,
        headers: dict[str, str] = None,
        get_data: dict[str, Any] = None,
        post_data: dict[str, Any] = None,
    ):
        if not headers:
            headers = {}
        if not headers.get("x-api-key"):
            _settings = settings.get_settings().payment_nowpayments
            if _settings.api_key:
                headers.update(
                    {
                        "x-api-key": _settings.api_key,
                    }
                )
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=Timeout(10.0), proxies=config.PROXY
            ) as client:
                url = cls.BASE_URL.rstrip("/") + "/" + path.lstrip("/")
                if method == "GET":
                    r = await client.get(url=url, params=get_data, headers=headers)
                    if r.status_code == 200:
                        return r.json()
                    raise NowPaymentsError(f"{r.text}")
                if method == "POST":
                    payload = (
                        {k: _json_value(v) for k, v in post_data.items()}
                        if post_data
                        else None
                    )
                    r = await client.post(url=url, json=payload)
                    if r.status_code in {200, 201}:
                        return r.json()
                    raise NowPaymentsError(f"{r.text}")
        except httpx.HTTPError as exc:
            raise NowPaymentsError(str(exc)) from exc

    @classmethod
    async def status(cls) -> bool:
        r = await cls._call_api(
            "GET",
            "/status",
        )
        if r:
            if r.get("message") == "OK":
                return True
        return False

    @classmethod
    async def get_available_currencies(
        cls, api_key: str = None
    ) -> dict[str, list[str]]:
        r = await cls._call_api(
            "GET",
            "/currencies",
            headers={"x-api-key": api_key},
        )
        return r

    @classmethod
    async def create_invoice(
        cls,
        price_amount: float | Decimal | str,
        order_id: int | str,
        order_description: str = "",
        price_currency: str = "usd",
        ipn_callback_url: str | None = None,
        success_url: str | None = None,
        cancel_url: str | None = None,
        partially_paid_url: str | None = None,
        is_fixed_rate: bool = True,
        is_fee_paid_by_user: bool | None = None,
    ):
        callback_url = ipn_callback_url or config.PUBLIC_BASE_URL + "/npipn"
        try:
            amount_for_fee = float(price_amount)
        except (TypeError, ValueError):
            amount_for_fee = 0.0
        data = {
            "price_amount": price_amount,
            "price_currency": price_currency,
            "order_id": order_id,
            "order_description": order_description,
            "ipn_callback_url": callback_url,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "partially_paid_url": partially_paid_url,
            "is_fixed_rate": is_fixed_rate,
            "is_fee_paid_by_user": (
                (False if amount_for_fee < 4.7 else True)
                if is_fee_paid_by_user is None
                else bool(is_fee_paid_by_user)
            ),
        }
        r = await cls._call_api(
            "POST",
            "/invoice",
            headers={"Content-Type": "application/json"},
            post_data={k: v for k, v in data.items() if v is not None},
        )
        return CreateInvoiceResponse(**r)

    @classmethod
    async def create_payment(
        cls,
        price_amount: float,
        pay_currency: str,
        order_id: int,
        price_currency: str = "usd",
    ) -> PaymentResponse:
        callback_url = config.PUBLIC_BASE_URL + "/npipn"
        data = {
            "price_amount": price_amount,
            "pay_currency": pay_currency,
            "price_currency": price_currency,
            "ipn_callback_url": callback_url,
            "order_id": order_id,
            "is_fee_paid_by_user": False if price_amount < 4.7 else True,
        }
        r = await cls._call_api(
            "POST",
            "/payment",
            headers={"Content-Type": "application/json"},
            post_data=data,
        )
        return PaymentResponse(**r)

    @classmethod
    async def get_payment_status(cls, payment_id: str) -> PaymentResponse:
        r = await cls._call_api("GET", f"/payment/{payment_id}")
        return PaymentResponse(**r)

    @classmethod
    async def get_payments(
        cls,
        *,
        invoice_id: str | int | None = None,
        limit: int = 10,
        page: int = 0,
        sort_by: str = "created_at",
        order_by: str = "desc",
    ) -> list[PaymentResponse]:
        query: dict[str, Any] = {
            "limit": max(1, min(int(limit or 10), 100)),
            "page": max(0, int(page or 0)),
            "sortBy": sort_by,
            "orderBy": order_by,
        }
        if invoice_id:
            query["invoiceId"] = str(invoice_id)
        r = await cls._call_api("GET", "/payment/", get_data=query)
        rows = r.get("data") if isinstance(r, dict) else r
        if not isinstance(rows, list):
            return []
        out: list[PaymentResponse] = []
        for item in rows:
            if isinstance(item, dict):
                try:
                    out.append(PaymentResponse(**item))
                except Exception:
                    continue
        return out

    @classmethod
    async def get_minimum_amount(
        cls, currency_from: str, currency_to: str, fiat_equivalent: str = "usd"
    ) -> MinAmountResponse:
        r = await cls._call_api(
            "GET",
            "/min-amount",
            get_data={
                "currency_from": currency_from,
                "currency_to": currency_to,
                "fiat_equivalent": fiat_equivalent,
            },
        )
        return MinAmountResponse(**r)


class EswapError(Exception):
    pass


class EswapResponse(BaseModel):
    status: str
    message: str | None = None
    result: Any = None


class EswapPaymentResponse(BaseModel):
    tracking_code: str
    token: str
    url: str
    link: str


class EswapAPI:
    BASE_URL = config.ESWAP_API_URL

    @classmethod
    async def _call_api(
        cls,
        method: Literal["GET", "POST"],
        path: str,
        headers: dict[str, str] = None,
        get_data: dict[str, Any] = None,
        post_data: dict[str, Any] = None,
    ):
        if not headers:
            headers = {}
        async with httpx.AsyncClient(headers=headers) as client:
            url = cls.BASE_URL.rstrip("/") + "/" + path.lstrip("/")
            if method == "GET":
                if get_data:
                    url = url + "?" + get_parsed_query_parameters(data=get_data)
                r = await client.get(url=url)
                if r.status_code == 200:
                    return r.json()
                else:
                    raise EswapError(f"{r.text}")
            elif method == "POST":
                r = await client.post(url=url, json=post_data)
                if r.status_code in {200, 201}:
                    return EswapResponse.model_validate(r.json())
                else:
                    raise EswapError(f"{r.text}")

    @classmethod
    async def payment(
        cls,
        amount: float,
        wallet: str,
        currency: str = "coin",
    ) -> EswapPaymentResponse:
        data = {
            "merchant_id": settings.get_settings().payment_eswap.api_key,
            "wallet": wallet,
            "amount": amount,
            "currency": currency,
        }
        r = await cls._call_api(
            "POST",
            "/api/v1/gw/payment",
            headers={"Content-Type": "application/json"},
            post_data={k: v for k, v in data.items() if v is not None},
        )
        return EswapPaymentResponse.model_validate(r.result)
