import json
from datetime import datetime as dt
from typing import Any

import aiohttp_jinja2
import httpx
from aiohttp import web
from tortoise.transactions import in_transaction

from app.logger import get_logger
from app.main import bot, get_bot_username
from app.models.user import RialGatewayPayment, Transaction
from app.plugins.payment import jobs
from app.utils import helpers, settings
from app.utils.rate_limit import RateLimit

from .clients import AqayePardakhtAPI, GatewayError, PaypingAPI, ZarinpalAPI, ZibalAPI

routes = web.RouteTableDef()


logger = get_logger("payment/rialgateway/web")


async def payping_verify_payment(
    transaction: Transaction, data: dict[str, Any]
) -> dict[str, Any]:
    if await RateLimit.throttled(None, transaction.id, key="trx_payping", count=1):
        return {
            "status_code": 429,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": "تعداد درخواست‌های شما زیاد است! لطفا کمی بعد دوباره تلاش کنید...",
            },
        }
    _settings = settings.get_settings().payment_payping
    if transaction.status != Transaction.Status.finished:
        try:
            async with in_transaction():
                amount = transaction.amount - transaction.amount_free_given
                verify = await PaypingAPI.verify(
                    amount=amount,
                    ref_id=data.get("refid"),
                )
                await Transaction.filter(id=transaction.id).update(
                    status=Transaction.Status.finished,
                    amount_paid=verify.amount,
                    finished_at=dt.now(),
                )
                await transaction.refresh_from_db()
                await RialGatewayPayment.filter(transaction_id=transaction.id).update(
                    data=verify.model_dump(mode="json")
                )
            text = f"""
✅ پرداخت شما از طریق {_settings.menu_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{verify.amount:,}</b> تومان
‌‌
"""
            msg = await bot.send_message(transaction.user_id, text)
            helpers.transaction_log(
                transaction=transaction, payment=transaction.rialgateway_payment
            )
            jobs.activate_service(transaction, msg)
            return {
                "status_code": 200,
                "data": {
                    "status": True,
                    "amount": f"{amount:,}",
                    "order_id": transaction.id,
                    "ref_id": data.get("transid"),
                },
            }
        except GatewayError as exc:
            logger.error(exc)
            return {
                "status_code": (
                    exc.result.pop("status_code", None) if exc.result else 400
                ),
                "data": dict(
                    {
                        "status": False,
                        "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                        "order_id": transaction.id,
                        "message": str(exc),
                    },
                    **exc.result if exc.result else {},
                ),
            }
        except httpx.ReadTimeout as exc:
            logger.error(exc)
            return {
                "status_code": 504,
                "data": {
                    "status": False,
                    "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                    "order_id": transaction.id,
                    "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
                },
            }
    else:
        return {
            "status_code": 200,
            "data": {
                "status": True,
                "already_paid": True,
                "amount": f"{transaction.amount_paid:,}",
                "order_id": transaction.id,
                "ref_id": data.get("transid"),
                "message": "تراکنش قبلا تأیید شده است",
            },
        }


async def aqaye_pardakht_veriy_payment(
    transaction: Transaction, data: dict[str, Any]
) -> dict[str, Any]:
    if data.get("status", None) == "0":
        return {
            "status_code": 400,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": "پرداخت انجام نشد!",
            },
        }
    if await RateLimit.throttled(
        None, transaction.id, key="trx_aqaye_pardakht", count=1
    ):
        return {
            "status_code": 429,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": "تعداد درخواست‌های شما زیاد است! لطفا کمی بعد دوباره تلاش کنید...",
            },
        }
    _settings = settings.get_settings().payment_aqaye_pardakht
    if transaction.status != Transaction.Status.finished:
        try:
            async with in_transaction():
                amount = transaction.amount - transaction.amount_free_given
                verify = await AqayePardakhtAPI.verify(
                    amount=amount,
                    ref_id=data.get("transid"),
                )
                await Transaction.filter(id=transaction.id).update(
                    status=Transaction.Status.finished,
                    amount_paid=amount,
                    finished_at=dt.now(),
                )
                await transaction.refresh_from_db()
                await RialGatewayPayment.filter(transaction_id=transaction.id).update(
                    data=verify.model_dump(mode="json")
                )
            text = f"""
✅ پرداخت شما از طریق {_settings.menu_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{amount:,}</b> تومان
‌‌
"""
            msg = await bot.send_message(transaction.user_id, text)
            helpers.transaction_log(
                transaction=transaction, payment=transaction.rialgateway_payment
            )
            jobs.activate_service(transaction, msg)
            return {
                "status_code": 200,
                "data": {
                    "status": True,
                    "amount": f"{amount:,}",
                    "order_id": transaction.id,
                    "ref_id": data.get("transid"),
                },
            }
        except GatewayError as exc:
            logger.error(exc)
            return {
                "status_code": (
                    exc.result.pop("status_code", None) if exc.result else 400
                ),
                "data": dict(
                    {
                        "status": False,
                        "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                        "order_id": transaction.id,
                        "message": exc.result.pop("message", "خطای نامشخص!")
                        if exc.result
                        else "خطای نامشخص!",
                    },
                ),
            }
        except httpx.ReadTimeout as exc:
            logger.error(exc)
            return {
                "status_code": 504,
                "data": {
                    "status": False,
                    "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                    "order_id": transaction.id,
                    "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
                },
            }
    else:
        return {
            "status_code": 200,
            "data": {
                "status": True,
                "already_paid": True,
                "amount": f"{transaction.amount_paid:,}",
                "order_id": transaction.id,
                "ref_id": data.get("transid"),
                "message": "تراکنش قبلا تأیید شده است",
            },
        }


async def zibal_verify_payment(
    transaction: Transaction, data: dict[str, Any]
) -> dict[str, Any]:
    if await RateLimit.throttled(None, transaction.id, key="trx_zibal", count=1):
        return {
            "status_code": 429,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": "تعداد درخواست‌های شما زیاد است! لطفا کمی بعد دوباره تلاش کنید...",
            },
        }
    _settings = settings.get_settings().payment_zibal
    if transaction.status != Transaction.Status.finished:
        try:
            async with in_transaction():
                amount = transaction.amount - transaction.amount_free_given
                verify = await ZibalAPI.verify(
                    amount=amount,
                    ref_id=data.get("trackId"),
                )
                await Transaction.filter(id=transaction.id).update(
                    status=Transaction.Status.finished,
                    amount_paid=verify.amount / 10
                    if verify.amount
                    else transaction.amount,
                    finished_at=dt.now(),
                )
                await transaction.refresh_from_db()
                await RialGatewayPayment.filter(transaction_id=transaction.id).update(
                    data=verify.model_dump(mode="json")
                )
            text = f"""
✅ پرداخت شما از طریق {_settings.menu_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{verify.amount or transaction.amount:,}</b> تومان
‌‌
"""
            msg = await bot.send_message(transaction.user_id, text)
            helpers.transaction_log(
                transaction=transaction, payment=transaction.rialgateway_payment
            )
            jobs.activate_service(transaction, msg)
            return {
                "status_code": 200,
                "data": {
                    "status": True,
                    "amount": f"{amount:,}",
                    "order_id": transaction.id,
                    "ref_id": data.get("transid"),
                },
            }
        except GatewayError as exc:
            if exc.result.get("result") == 202:
                message = "تراکنش ناموفق!"
            else:
                logger.error(exc)
                message = str(exc)
            return {
                "status_code": (
                    exc.result.pop("status_code", None) if exc.result else 400
                ),
                "data": dict(
                    {
                        "status": False,
                        "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                        "order_id": transaction.id,
                        "message": message,
                    },
                    **exc.result if exc.result else {},
                ),
            }
        except httpx.ReadTimeout as exc:
            logger.error(exc)
            return {
                "status_code": 504,
                "data": {
                    "status": False,
                    "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                    "order_id": transaction.id,
                    "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
                },
            }
    else:
        return {
            "status_code": 200,
            "data": {
                "status": True,
                "already_paid": True,
                "amount": f"{transaction.amount_paid:,}",
                "order_id": transaction.id,
                "ref_id": data.get("transid"),
                "message": "تراکنش قبلا تأیید شده است",
            },
        }


async def zarinpal_verify_payment(
    transaction: Transaction, data: dict[str, Any]
) -> dict[str, Any]:
    if await RateLimit.throttled(None, transaction.id, key="trx_zarinpal", count=1):
        return {
            "status_code": 429,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": "تعداد درخواست‌های شما زیاد است! لطفا کمی بعد دوباره تلاش کنید...",
            },
        }
    _settings = settings.get_settings().payment_zarinpal
    if transaction.status != Transaction.Status.finished:
        try:
            async with in_transaction():
                amount = transaction.amount - transaction.amount_free_given
                verify = await ZarinpalAPI.verify(
                    amount=amount,
                    ref_id=data.get("Authority"),
                )
                if verify.code == 101:
                    return {
                        "status_code": 200,
                        "data": {
                            "status": True,
                            "already_paid": True,
                            "amount": f"{amount:,}",
                            "order_id": transaction.id,
                            "ref_id": verify.ref_id,
                            "message": "تراکنش قبلا تأیید شده است",
                        },
                    }
                if verify.code != 100:
                    return {
                        "status_code": 400,
                        "data": dict(
                            {
                                "status": False,
                                "order_id": transaction.id,
                            },
                            **verify.model_dump(),
                        ),
                    }
                await Transaction.filter(id=transaction.id).update(
                    status=Transaction.Status.finished,
                    amount_paid=amount,
                    finished_at=dt.now(),
                )
                await transaction.refresh_from_db()
                await RialGatewayPayment.filter(transaction_id=transaction.id).update(
                    data=verify.model_dump(mode="json")
                )
            text = f"""
✅ پرداخت شما از طریق {_settings.menu_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount:,}</b> تومان
‌‌
"""
            msg = await bot.send_message(transaction.user_id, text)
            helpers.transaction_log(
                transaction=transaction, payment=transaction.rialgateway_payment
            )
            jobs.activate_service(transaction, msg)
            return {
                "status_code": 200,
                "data": {
                    "status": True,
                    "amount": f"{amount:,}",
                    "order_id": transaction.id,
                    "ref_id": verify.ref_id,
                },
            }
        except GatewayError as exc:
            logger.error(exc)
            return {
                "status_code": (
                    exc.result.pop("status_code", None) if exc.result else 400
                ),
                "data": dict(
                    {
                        "status": False,
                        "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                        "order_id": transaction.id,
                        "message": str(exc),
                    },
                    **exc.result if exc.result else {},
                ),
            }
        except httpx.ReadTimeout as exc:
            logger.error(exc)
            return {
                "status_code": 504,
                "data": {
                    "status": False,
                    "amount": f"{transaction.amount - transaction.amount_free_given:,}",
                    "order_id": transaction.id,
                    "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
                },
            }
    else:
        return {
            "status_code": 200,
            "data": {
                "status": True,
                "already_paid": True,
                "amount": f"{transaction.amount_paid:,}",
                "order_id": transaction.id,
                "message": "تراکنش قبلا تأیید شده است",
            },
        }


async def transaction_verify(
    transaction: Transaction, data: dict[str, Any]
) -> dict[str, str]:
    payment: RialGatewayPayment = transaction.rialgateway_payment
    if not payment:
        return {
            "status_code": 404,
            "order_id": transaction.id,
            "data": {"status": False, "message": "پرداختی برای این تراکنش یافت نشد"},
        }

    if payment.provider == RialGatewayPayment.Provider.payping:
        return await payping_verify_payment(transaction, data)
    elif payment.provider == RialGatewayPayment.Provider.aqaye_pardakht:
        return await aqaye_pardakht_veriy_payment(transaction, data)
    elif payment.provider == RialGatewayPayment.Provider.zibal:
        return await zibal_verify_payment(transaction, data)
    elif payment.provider == RialGatewayPayment.Provider.zarinpal:
        return await zarinpal_verify_payment(transaction, data)
    else:
        return {
            "status_code": 400,
            "data": {
                "status": False,
                "order_id": transaction.id,
                "message": f"Payment Provider {payment.provider.value!r} is not supported with this method",
            },
        }


def get_id_from_data(data: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if (value := data.get(key, None)) is not None:
            return int(value)


async def parse_request_data(request: web.Request, log_key: str = "") -> dict[str, Any]:
    text = await request.text()
    logger.info(f"got {log_key} verify request: {text}")
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = {item.split("=")[0]: item.split("=")[1] for item in text.split("&")}
    return data


KEYS = ["orderId", "invoice_id", "clientrefid", "order_id"]


@routes.post("/pay-json/")
@routes.post("/pay-json")
async def verify_payment(request: web.Request):
    if not request.can_read_body:
        return

    try:
        data = await parse_request_data(request, "pay-json")
    except (ValueError, IndexError):
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=422
        )

    if not data:
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=400
        )
    try:
        trx_id = get_id_from_data(data=data, keys=KEYS)
        if not trx_id:
            return web.json_response(
                {
                    "status": False,
                    "message": "one of the keys " + ", ".join(KEYS) + " is required",
                },
                status=400,
            )
    except ValueError:
        return web.json_response(
            {
                "status": False,
                "message": "keys " + ", ".join(KEYS) + " must be a valid integer",
            },
            status=400,
        )

    transaction = (
        await Transaction.filter(id=trx_id)
        .prefetch_related("rialgateway_payment")
        .first()
    )
    if not transaction:
        return web.json_response(
            {
                "status": False,
                "message": f"تراکنش {trx_id} یافت نشد",
            },
            status=404,
        )
    if transaction.type != Transaction.PaymentType.rial_gateway:
        return web.json_response(
            {
                "status": False,
                "order_id": trx_id,
                "message": "Transaction type mismatch",
            },
            status=400,
        )
    result = await transaction_verify(transaction, data)
    if result:
        return web.json_response(
            result.get("data", {"status": False}), status=result.get("status_code", 400)
        )
    return web.json_response(
        {"status": False, "order_id": trx_id, "message": "خطای نامشخص!"}, status=400
    )


@routes.post("/payping")
@routes.post("/payping/")
async def verify_payment(request: web.Request):  # noqa: F811
    if not request.can_read_body:
        return

    try:
        data = await parse_request_data(request, "payping")
    except (ValueError, IndexError):
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=422
        )

    trx_id = data.get("clientrefid")
    if not trx_id or not trx_id.isnumeric():
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if data.get("refid") is None:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "order_id": trx_id,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    transaction = (
        await Transaction.filter(id=int(trx_id))
        .prefetch_related("rialgateway_payment")
        .first()
    )
    if not transaction or not transaction.rialgateway_payment:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "message": "پرداخت مورد نظر یافت نشد!",
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    result = await payping_verify_payment(transaction, data)

    if result:
        result.update({"bot_url": f"https://t.me/{get_bot_username()}"})
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            result.get("data", {"status": False}),
            status=result.get("status_code", 400),
        )
    return aiohttp_jinja2.render_template(
        "payment.html",
        request,
        {
            "status": False,
            "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
            "bot_url": f"https://t.me/{get_bot_username()}",
        },
        status=400,
    )


@routes.post("/aqaye_pardakht")
@routes.post("/aqaye_pardakht/")
async def verify_payment(request: web.Request):  # noqa: F811
    if not request.can_read_body:
        return

    try:
        data = await parse_request_data(request, "aqaye_pardakht")
    except (ValueError, IndexError):
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=422
        )

    trx_id = data.get("invoice_id")
    if not trx_id or not trx_id.isnumeric():
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if data.get("transid") is None:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "order_id": trx_id,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if (status := data.get("status")) is not None:
        if int(status) == 0:
            return aiohttp_jinja2.render_template(
                "payment.html",
                request,
                {
                    "status": False,
                    "order_id": trx_id,
                    "bot_url": f"https://t.me/{get_bot_username()}",
                },
            )

    transaction = (
        await Transaction.filter(id=int(trx_id))
        .prefetch_related("rialgateway_payment")
        .first()
    )
    if not transaction or not transaction.rialgateway_payment:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "message": "پرداخت مورد نظر یافت نشد!",
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    result = await aqaye_pardakht_veriy_payment(transaction, data)
    if result:
        result.update({"bot_url": f"https://t.me/{get_bot_username()}"})
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            result.get("data", {"status": False}),
            status=result.get("status_code", 400),
        )
    return aiohttp_jinja2.render_template(
        "payment.html",
        request,
        {
            "status": False,
            "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
            "bot_url": f"https://t.me/{get_bot_username()}",
        },
        status=400,
    )


@routes.get("/zibal")
@routes.get("/zibal/")
async def verify_payment(request: web.Request):  # noqa: F811
    try:
        data = request.rel_url.query
    except (ValueError, IndexError):
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=422
        )

    trx_id = data.get("orderId")
    if not trx_id or not trx_id.isnumeric():
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if data.get("trackId") is None:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "order_id": trx_id,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    transaction = (
        await Transaction.filter(id=int(trx_id))
        .prefetch_related("rialgateway_payment")
        .first()
    )
    if not transaction or not transaction.rialgateway_payment:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "message": "پرداخت مورد نظر یافت نشد!",
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    result = await zibal_verify_payment(transaction, data)

    if result:
        result.update({"bot_url": f"https://t.me/{get_bot_username()}"})
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            result.get("data", {"status": False}),
            status=result.get("status_code", 400) or 400,
        )
    return aiohttp_jinja2.render_template(
        "payment.html",
        request,
        {
            "status": False,
            "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
            "bot_url": f"https://t.me/{get_bot_username()}",
        },
        status=400,
    )


@routes.get("/zarinpal")
@routes.get("/zarinpal/")
async def verify_payment(request: web.Request):  # noqa: F811
    try:
        data = request.rel_url.query
    except (ValueError, IndexError):
        return web.json_response(
            {"status": False, "message": "could not parse data"}, status=422
        )

    trx_id = data.get("order_id")
    if not trx_id or not trx_id.isnumeric():
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if data.get("Status") != "OK":
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )
    if data.get("Authority") is None:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "order_id": trx_id,
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    transaction = (
        await Transaction.filter(id=int(trx_id))
        .prefetch_related("rialgateway_payment")
        .first()
    )
    if not transaction or not transaction.rialgateway_payment:
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            {
                "status": False,
                "message": "پرداخت مورد نظر یافت نشد!",
                "bot_url": f"https://t.me/{get_bot_username()}",
            },
        )

    result = await zarinpal_verify_payment(transaction, data)

    if result:
        result.update({"bot_url": f"https://t.me/{get_bot_username()}"})
        return aiohttp_jinja2.render_template(
            "payment.html",
            request,
            result.get("data", {"status": False}),
            status=result.get("status_code", 400),
        )
    return aiohttp_jinja2.render_template(
        "payment.html",
        request,
        {
            "status": False,
            "message": "خطایی در تایید تراکنش اتفاق افتاد! لطفا صفحه را رفرش کنید.",
            "bot_url": f"https://t.me/{get_bot_username()}",
        },
        status=400,
    )
