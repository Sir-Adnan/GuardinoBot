import hashlib
import hmac
import json
from datetime import datetime as dt
from typing import Any

from aiohttp import web
from tortoise.transactions import in_transaction

import config
from app.logger import get_logger
from app.main import bot
from app.models.user import CryptoPayment, Transaction
from app.plugins.payment import jobs
from app.utils import helpers, settings

from .clients import PaymentResponse
from .plisio import verify_callback as plisio_verify
from .plisio_service import (
    extract_order_number,
    extract_txn_id,
    finalize_plisio_payment,
    find_plisio_transaction,
)


def _to_float(v: Any):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

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
    (constant-time compare to avoid timing attacks).
    """
    if not sig or not key:
        return False
    return hmac.compare_digest(sig, hmac_sign(key, sort_data(data)))


def get_menu_title(
    provider: CryptoPayment.Provider, _settings: "settings.Settings"
) -> str:
    if provider == CryptoPayment.Provider.nowpayments:
        return _settings.payment_nowpayments.menu_title
    elif provider == CryptoPayment.Provider.plisio:
        return _settings.payment_plisio.menu_title
    elif provider == CryptoPayment.Provider.eswap:
        return _settings.payment_eswap.menu_title
    elif provider == CryptoPayment.Provider.swapino:
        return _settings.payment_swapino.menu_title
    return "-"


@routes.post("/npipn")
@routes.post("/npipn/")
async def verify_payment(request: web.Request):
    _settings = settings.get_settings()

    # Read the body defensively — it must be a JSON object.
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("payload is not a JSON object")
    except Exception:  # noqa: BLE001
        logger.warning("npipn: invalid or empty body")
        return web.Response(status=400, text="bad request")

    # SECURITY: the IPN signature is MANDATORY. Without a configured secret we
    # cannot prove the callback really came from NowPayments — an attacker could
    # POST a forged "finished" notification for any order_id and self-credit. So
    # reject when no secret is set (and on any signature mismatch).
    secret = _settings.payment_nowpayments.ipn_secret_key
    if not secret:
        logger.error(
            "npipn: IPN secret key is NOT configured — rejecting callback. Set the "
            "IPN secret in the NowPayments gateway settings to credit crypto safely."
        )
        return web.Response(status=403, text="ipn secret not configured")
    sig = request.headers.get("x-nowpayments-sig", "")
    if not verify_signature(sig, secret, data):
        logger.error("npipn: signature verification failed")
        return web.Response(status=403, text="invalid signature")

    # authenticated — log only non-sensitive identifiers
    logger.info(
        f"npipn verified: order_id={data.get('order_id')} "
        f"status={data.get('payment_status')}"
    )

    try:
        payment = PaymentResponse(**data)
    except Exception as exc:  # noqa: BLE001 - acknowledge but can't act on a bad shape
        logger.error(f"npipn: could not parse verified payload: {exc}")
        return web.Response(status=200)
    transaction = await Transaction.filter(id=payment.order_id).first()
    if not transaction:
        logger.error(f"npipn: transaction {payment.order_id} not found")
        return web.Response(status=200)

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


async def _read_plisio_payload(request: web.Request) -> dict[str, Any]:
    wants_json = request.query.get("json") == "true"
    content_type = (request.content_type or "").lower()
    if wants_json or "json" in content_type:
        try:
            data = await request.json()
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            if wants_json:
                raise
    return dict(await request.post())


@routes.get("/payments/plisio/success")
async def plisio_success(request: web.Request):
    return web.Response(text="Payment result will be checked by the bot.")


@routes.get("/payments/plisio/fail")
async def plisio_fail(request: web.Request):
    return web.Response(text="Payment was not completed.")


@routes.post("/payments/plisio/callback")
@routes.post("/payments/plisio/callback/")
async def verify_plisio_payment_v2(request: web.Request):
    _settings = settings.get_settings()
    api_key = _settings.payment_plisio.api_key
    if not api_key:
        logger.error("plisio: API key not configured - rejecting callback")
        return web.Response(status=403, text="not configured")

    try:
        payload = await _read_plisio_payload(request)
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="bad request")
    if not payload:
        return web.Response(status=400, text="empty body")
    if not plisio_verify(payload, api_key):
        logger.error("plisio: verify_hash verification failed")
        return web.Response(status=403, text="invalid signature")

    order_number = extract_order_number(payload)
    txn_id = extract_txn_id(payload)
    transaction = await find_plisio_transaction(
        order_number=order_number, txn_id=txn_id
    )
    if not transaction:
        logger.warning(
            f"plisio: callback for unknown transaction order={order_number} txn={txn_id}"
        )
        return web.json_response({"ok": True})

    result = await finalize_plisio_payment(transaction, payload, source="callback")
    return web.json_response({"ok": True, **result})


@routes.post("/plisio")
@routes.post("/plisio/")
async def verify_plisio_payment(request: web.Request):
    """Plisio callback. SECURITY: the API key is mandatory and the `verify_hash`
    (HMAC-SHA1 over PHP-serialize, byte-exact) is verified — without it an
    attacker could forge a "completed" callback and self-credit. Read as form
    data (PHP `$_POST` → string values) so the signature matches."""
    _settings = settings.get_settings()
    api_key = _settings.payment_plisio.api_key

    try:
        post = dict(await request.post())
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="bad request")
    if not post:
        return web.Response(status=400, text="empty body")

    if not api_key:
        logger.error("plisio: API key not configured — rejecting callback")
        return web.Response(status=403, text="not configured")
    if not plisio_verify(post, api_key):
        logger.error("plisio: verify_hash verification failed")
        return web.Response(status=403, text="invalid signature")

    order_id = post.get("order_number")
    status_val = str(post.get("status") or "").lower()
    logger.info(f"plisio verified: order={order_id} status={status_val}")

    transaction = await Transaction.filter(id=order_id).first()
    if not transaction:
        logger.error(f"plisio: transaction {order_id} not found")
        return web.Response(status=200)

    if status_val == "completed" and transaction.status not in (
        Transaction.Status.finished,
        Transaction.Status.partially_paid,
    ):
        async with in_transaction():
            await transaction.fetch_related("crypto_payment")
            cp = transaction.crypto_payment
            transaction.status = Transaction.Status.finished
            transaction.finished_at = dt.now()
            # balance credits transaction.amount (status=finished); amount_paid is a record
            transaction.amount_paid = int((cp.usdt_rate or 0) * (cp.price_amount or 0))
            await transaction.save()
            await cp.update_from_dict(
                {
                    "payment_status": CryptoPayment.PaymentStatus.finished,
                    "pay_currency": post.get("psys_cid") or post.get("currency"),
                    "pay_amount": _to_float(post.get("amount")),
                    "outcome_amount": _to_float(post.get("amount")),
                    "pay_address": post.get("wallet_hash"),
                }
            ).save()
        text = f"""
✅ پرداخت شما از طریق {_settings.payment_plisio.menu_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
‌‌
"""
        msg = await bot.send_message(transaction.user_id, text)
        await transaction.fetch_related("crypto_payment")
        helpers.transaction_log(
            transaction=transaction, payment=transaction.crypto_payment
        )
        jobs.activate_service(transaction, msg)
    elif status_val == "mismatch":
        # under/over-paid: NEVER auto-credit the full amount — flag for review.
        logger.warning(f"plisio: MISMATCH on tx {order_id} — manual review needed")
        for uid in config.SUPER_USERS:
            try:
                await bot.send_message(
                    uid,
                    "⚠️ پرداختِ Plisio با مبلغِ نامتناظر (mismatch) برای فاکتور "
                    f"<code>{order_id}</code> دریافت شد — نیاز به بررسیِ دستی.",
                )
            except Exception:  # noqa: BLE001
                pass
    elif status_val in (
        "confirming",
        "pending",
        "pending internal",
    ) and transaction.status != Transaction.Status.confirming:
        await Transaction.filter(id=transaction.id).update(
            status=Transaction.Status.confirming
        )
        try:
            await bot.send_message(
                transaction.user_id,
                f"♻️ وضعیت فاکتور <code>{transaction.id}</code> به «در حال تأیید» تغییر کرد!",
            )
        except Exception:  # noqa: BLE001
            pass
    return web.Response(status=200)
