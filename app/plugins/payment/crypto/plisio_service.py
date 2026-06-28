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

from .plisio import (
    FAILED_STATUSES,
    PENDING_STATUSES,
    STATUS_COMPLETED,
    STATUS_MISMATCH,
    PlisioAPI,
    PlisioError,
)

logger = get_logger("plugins/payment/plisio")
PLISIO_REVIEW_QUEUE = "plisio:review:queue"


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


def tracking_code(transaction_id: int | str) -> str:
    return f"GB-{transaction_id}"


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

🧾 کد پیگیری: <code>{tracking_code(transaction.id)}</code>
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


async def manual_approve_plisio_payment(
    transaction: Transaction,
    *,
    source: str,
    actor_id: int | None = None,
) -> str:
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.plisio:
        return "ignored"
    if transaction.status in (
        Transaction.Status.finished,
        Transaction.Status.partially_paid,
    ):
        return "already_finished"

    extra = dict(cp.extra_data or {})
    extra["status_source"] = source
    extra["plisio_status"] = "manual_approved"
    extra["manual_approved"] = True
    extra["manual_approved_at"] = dt.now().isoformat()
    if actor_id is not None:
        extra["manual_approved_by"] = actor_id

    async with in_transaction():
        await transaction.fetch_related("crypto_payment")
        cp = transaction.crypto_payment
        transaction.status = Transaction.Status.finished
        transaction.finished_at = dt.now()
        transaction.amount_paid = max(0, transaction.amount - transaction.amount_free_given)
        await transaction.save()
        cp.payment_status = CryptoPayment.PaymentStatus.finished
        cp.extra_data = extra
        await cp.save()

    text = f"""
✅ پرداخت شما با بررسی دستی ادمین تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد.

🧾 کد پیگیری: <code>{tracking_code(transaction.id)}</code>
"""
    try:
        msg = await bot.send_message(transaction.user_id, text)
    except Exception:  # noqa: BLE001
        msg = None
    await transaction.fetch_related("crypto_payment")
    helpers.transaction_log(transaction=transaction, payment=transaction.crypto_payment)
    jobs.activate_service(transaction, msg)
    return "manual_approved"


async def _fetch_plisio_transaction(transaction_id: int) -> Transaction | None:
    return await Transaction.filter(id=transaction_id).prefetch_related("crypto_payment").first()


async def _check_plisio_transaction(transaction: Transaction, *, source: str) -> dict[str, str]:
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.plisio:
        return {"result": "ignored", "status": ""}
    txn_id = cp.payment_id or cp.invoice_id
    if not txn_id:
        return {"result": "missing_txn_id", "status": ""}
    ps = settings.get_settings().payment_plisio
    operation = await PlisioAPI.get_operation(
        txn_id,
        api_key=ps.api_key,
        api_base=ps.api_base,
    )
    return await finalize_plisio_payment(transaction, operation, source=source)


async def process_plisio_review_queue() -> None:
    import json

    from app.main import redis

    for _ in range(50):
        raw = await redis.lpop(PLISIO_REVIEW_QUEUE)
        if not raw:
            break
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            item = json.loads(raw)
            transaction_id = int(item["transaction_id"])
            action = str(item.get("action") or "check")
            actor_id = int(item["actor_id"]) if item.get("actor_id") else None
        except Exception:  # noqa: BLE001
            continue
        transaction = await _fetch_plisio_transaction(transaction_id)
        if not transaction:
            continue
        try:
            if action == "approve":
                await manual_approve_plisio_payment(
                    transaction,
                    source="admin_manual",
                    actor_id=actor_id,
                )
            else:
                await _check_plisio_transaction(transaction, source="admin_check")
        except PlisioError:
            logger.warning(f"plisio admin check failed for transaction {transaction_id}")


async def auto_check_plisio_payments(limit: int = 10) -> None:
    ps = settings.get_settings().payment_plisio
    if not ps.enabled or not ps.api_key:
        return
    from app.main import redis

    rows = await (
        CryptoPayment.filter(
            provider=CryptoPayment.Provider.plisio,
            transaction__status__in=[
                Transaction.Status.waiting,
                Transaction.Status.confirming,
            ],
        )
        .prefetch_related("transaction")
        .order_by("created_at")
        .limit(limit)
    )
    for cp in rows:
        txn_id = cp.payment_id or cp.invoice_id
        if not txn_id:
            continue
        key = f"plisio:auto-check:{txn_id}"
        if await redis.get(key):
            continue
        await redis.set(key, "1", ex=60)
        try:
            await _check_plisio_transaction(cp.transaction, source="auto_check")
        except PlisioError:
            logger.warning(f"plisio auto-check failed for txn {txn_id}")
