"""Shared Plisio payment status handling.

Callback, user manual-check, and admin check must all pass through this module
so a paid invoice can only credit and activate once.
"""

from datetime import datetime as dt
from typing import Any

from tortoise.transactions import in_transaction

import config
from app.logger import get_logger
from app.main import bot
from app.models.user import CryptoPayment, Transaction
from app.plugins.payment import jobs
from app.utils import helpers, settings

from .plisio import FAILED_STATUSES, PENDING_STATUSES, STATUS_COMPLETED, STATUS_MISMATCH

logger = get_logger("plugins/payment/plisio")


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_payload(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def extract_order_number(payload: dict[str, Any]) -> str | None:
    order = payload.get("order_number")
    params = payload.get("params")
    if not order and isinstance(params, dict):
        order = params.get("order_number")
    return str(order).strip() if order not in (None, "") else None


def extract_txn_id(payload: dict[str, Any]) -> str | None:
    txn_id = (
        payload.get("txn_id")
        or payload.get("id")
        or payload.get("parent_id")
        or payload.get("paid_id")
    )
    return str(txn_id).strip() if txn_id not in (None, "") else None


def extract_status(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or "").strip().lower()


async def find_plisio_transaction(
    *,
    order_number: str | None = None,
    txn_id: str | None = None,
) -> Transaction | None:
    if order_number:
        try:
            return await Transaction.filter(id=int(order_number)).first()
        except (TypeError, ValueError):
            pass
    if not txn_id:
        return None
    cp = await CryptoPayment.filter(
        provider=CryptoPayment.Provider.plisio, invoice_id=txn_id
    ).first()
    if not cp:
        cp = await CryptoPayment.filter(
            provider=CryptoPayment.Provider.plisio, payment_id=txn_id
        ).first()
    if not cp:
        return None
    return await Transaction.filter(id=cp.transaction_id).first()


def _merge_extra(cp: CryptoPayment, payload: dict[str, Any], source: str) -> dict:
    extra = dict(cp.extra_data or {})
    key = "last_callback" if source == "callback" else "last_operation"
    extra[key] = _safe_payload(payload)
    extra["status_source"] = source
    extra["plisio_status"] = extract_status(payload)
    return extra


async def _alert_mismatch(transaction: Transaction, payload: dict[str, Any]) -> None:
    txn_id = extract_txn_id(payload) or "-"
    for uid in config.SUPER_USERS:
        try:
            await bot.send_message(
                uid,
                "⚠️ پرداخت Plisio با وضعیت mismatch دریافت شد.\n"
                f"فاکتور: <code>{transaction.id}</code>\n"
                f"Txn: <code>{txn_id}</code>\n"
                "این پرداخت به‌صورت خودکار شارژ نشد و نیاز به بررسی دستی دارد.",
            )
        except Exception:  # noqa: BLE001
            logger.warning(f"plisio mismatch alert failed for admin {uid}")


async def finalize_plisio_payment(
    transaction: Transaction,
    payload: dict[str, Any],
    *,
    source: str,
) -> dict[str, str]:
    status = extract_status(payload)
    if not status:
        return {"result": "unknown", "status": ""}

    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.plisio:
        return {"result": "ignored", "status": status}

    extra = _merge_extra(cp, payload, source)

    if transaction.status in (
        Transaction.Status.finished,
        Transaction.Status.partially_paid,
    ):
        cp.extra_data = extra
        await cp.save(update_fields=["extra_data"])
        return {"result": "already_finished", "status": status}

    if status == STATUS_COMPLETED:
        async with in_transaction():
            await transaction.fetch_related("crypto_payment")
            cp = transaction.crypto_payment
            extra = _merge_extra(cp, payload, source)
            transaction.status = Transaction.Status.finished
            transaction.finished_at = dt.now()
            transaction.amount_paid = max(0, transaction.amount - transaction.amount_free_given)
            await transaction.save()
            cp.payment_status = CryptoPayment.PaymentStatus.finished
            cp.payment_id = extract_txn_id(payload) or cp.payment_id
            cp.pay_currency = payload.get("psys_cid") or payload.get("currency") or cp.pay_currency
            try:
                cp.pay_amount = float(payload.get("amount") or payload.get("actual_sum") or 0)
            except (TypeError, ValueError):
                cp.pay_amount = cp.pay_amount
            cp.outcome_amount = cp.pay_amount
            cp.outcome_currency = cp.pay_currency
            tx_id = payload.get("tx_id")
            cp.purchase_id = ",".join(tx_id) if isinstance(tx_id, list) else tx_id
            cp.pay_address = payload.get("wallet_hash") or cp.pay_address
            cp.extra_data = extra
            await cp.save()

        title = settings.get_settings().payment_plisio.menu_title
        text = f"""
✅ پرداخت شما از طریق {title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount_paid:,}</b> تومان
"""
        msg = await bot.send_message(transaction.user_id, text)
        await transaction.fetch_related("crypto_payment")
        helpers.transaction_log(transaction=transaction, payment=transaction.crypto_payment)
        jobs.activate_service(transaction, msg)
        return {"result": "completed", "status": status}

    if status in PENDING_STATUSES:
        new_status = (
            Transaction.Status.waiting if status == "new" else Transaction.Status.confirming
        )
        cp_status = (
            CryptoPayment.PaymentStatus.waiting
            if status == "new"
            else CryptoPayment.PaymentStatus.confirming
        )
        await Transaction.filter(id=transaction.id).update(status=new_status)
        await CryptoPayment.filter(id=cp.id).update(
            payment_status=cp_status,
            extra_data=extra,
        )
        return {"result": "pending", "status": status}

    if status in FAILED_STATUSES:
        tx_status = (
            Transaction.Status.canceled
            if status in {"cancelled", "canceled"}
            else Transaction.Status.failed
        )
        cp_status = (
            CryptoPayment.PaymentStatus.expired
            if status == "expired"
            else CryptoPayment.PaymentStatus.failed
        )
        await Transaction.filter(id=transaction.id).update(status=tx_status)
        await CryptoPayment.filter(id=cp.id).update(
            payment_status=cp_status,
            extra_data=extra,
        )
        if status == STATUS_MISMATCH:
            await _alert_mismatch(transaction, payload)
        return {"result": "failed", "status": status}

    cp.extra_data = extra
    await cp.save(update_fields=["extra_data"])
    return {"result": "unknown", "status": status}
