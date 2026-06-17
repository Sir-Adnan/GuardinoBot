import hashlib
import hmac
import json
from datetime import datetime as dt
from typing import Any

from aiohttp import web
from tortoise.transactions import in_transaction

from app.logger import get_logger
from app.main import bot
from app.models.user import CryptoPayment, Transaction
from app.plugins.payment import jobs
from app.utils import helpers, settings

from .clients import PaymentResponse

logger = get_logger("plugins/payment/crypto")

routes = web.RouteTableDef()


def hmac_sign(key: str, data: str) -> str:
    """
    sign data string with key and sha512 algorithm
    """
    return hmac.new(
        key.encode(),
        data.encode(),
        hashlib.sha512,
    ).hexdigest()


def sort_data(data: dict[str, Any]) -> str:
    """
    sort data from nowpayments notification for hmac_sign
    """

    def _sort_dict(data_dict: dict[str, Any]) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    k: _sort_dict(v) if isinstance(v, dict) else v
                    for k, v in data_dict.items()
                }.items()
            )
        )

    return json.dumps(_sort_dict(data), separators=(",", ":"))


def verify_signature(sig: str, key: str, data: dict) -> bool:
    """
    verify nowpayments notification data with ipn secret key and signature
    """
    if sig == hmac_sign(key, sort_data(data)):
        return True
    return False


def get_menu_title(
    provider: CryptoPayment.Provider, _settings: "settings.Settings"
) -> str:
    if provider == CryptoPayment.Provider.nowpayments:
        return _settings.payment_nowpayments.menu_title
    elif provider == CryptoPayment.Provider.eswap:
        return _settings.payment_eswap.menu_title
    elif provider == CryptoPayment.Provider.swapino:
        return _settings.payment_swapino.menu_title
    return "-"


@routes.post("/npipn")
@routes.post("/npipn/")
async def verify_payment(request: web.Request):
    _settings = settings.get_settings()
    if not request.can_read_body:
        return
    data = await request.json()
    logger.info(f"got ipn from nowpayments: {data}")
    if _settings.payment_nowpayments.ipn_secret_key:
        nowpayments_sig = request.headers.get("x-nowpayments-sig")
        if not verify_signature(
            nowpayments_sig, _settings.payment_nowpayments.ipn_secret_key, data
        ):
            logger.error(f"Failed to verify ipn with secret key {nowpayments_sig}")
            return

    payment = PaymentResponse(**data)
    transaction = await Transaction.filter(id=payment.order_id).first()
    if not transaction:
        logger.error(f"Transaction {payment.order_id} not found")
        return

    if payment.payment_status == "finished" and (
        transaction.status
        not in [Transaction.Status.finished, Transaction.Status.partially_paid]
    ):
        async with in_transaction():
            await transaction.fetch_related("crypto_payment")
            transaction.status = Transaction.Status.finished
            transaction.finished_at = dt.now()
            transaction.amount_paid = (
                transaction.crypto_payment.usdt_rate * payment.price_amount
            )
            await transaction.save()
            await transaction.refresh_from_db()
            await transaction.crypto_payment.update_from_dict(
                {
                    "payment_id": payment.payment_id,
                    "pay_currency": payment.pay_currency,
                    "pay_amount": payment.pay_amount,
                    "nowpm_updated_at": payment.updated_at,
                    "payment_status": CryptoPayment.PaymentStatus.finished,
                    "outcome_amount": payment.outcome_amount,
                    "outcome_currency": payment.outcome_currency,
                    "purchase_id": payment.purchase_id,
                    "pay_address": payment.pay_address,
                    "fee": payment.fee,
                }
            ).save()
        gateway_title = get_menu_title(
            provider=transaction.crypto_payment.provider, _settings=_settings
        )
        text = f"""
✅ پرداخت شما از طریق {gateway_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount_paid:,}</b> تومان
‌‌
"""
        msg = await bot.send_message(transaction.user_id, text)
        await transaction.fetch_related("crypto_payment")
        helpers.transaction_log(
            transaction=transaction, payment=transaction.crypto_payment
        )
        jobs.activate_service(transaction, msg)
    elif (
        payment.payment_status == "sending"
        and transaction.status != Transaction.Status.sending
    ):
        await Transaction.filter(id=transaction.id).update(
            status=Transaction.Status.sending
        )
        text = f"""
💠 وضعیت فاکتور پرداخت شما به شماره <code>{transaction.id}</code> به <b>«در حال ارسال»</b> تغییر کرد!
"""
        await bot.send_message(transaction.user_id, text)
    elif (
        payment.payment_status == "confirming"
        and transaction.status != Transaction.Status.confirming
    ):
        await Transaction.filter(id=transaction.id).update(
            status=Transaction.Status.confirming
        )
        text = f"""
♻️ وضعیت فاکتور پرداخت شما به شماره <code>{transaction.id}</code> به <b>«در حال تأیید»</b> تغییر کرد!
"""
        await bot.send_message(transaction.user_id, text)
    return web.Response(status=200)
