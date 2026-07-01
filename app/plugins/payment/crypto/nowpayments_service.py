"""Shared NowPayments payment status handling.

IPN callbacks, customer manual checks, web-panel checks, and manual approval all
go through this module so a crypto payment can only credit/activate once.
"""

import json
from datetime import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from tortoise.transactions import in_transaction

from app.logger import get_logger
from app.main import bot, redis
from app.models.user import CryptoPayment, Transaction
from app.plugins.payment import jobs
from app.utils import helpers, settings

from .clients import NowPaymentsAPI, NowPaymentsError, PaymentResponse

logger = get_logger("plugins/payment/nowpayments")

NOWPAYMENTS_REVIEW_QUEUE = "nowpayments:review:queue"

STATUS_FINISHED = "finished"
PENDING_STATUSES = {"waiting", "confirming", "confirmed"}
SENDING_STATUSES = {"sending"}
REVIEW_STATUSES = {"partially_paid"}
FAILED_STATUSES = {"failed", "refunded", "expired"}


def tracking_code(transaction_id: int | str) -> str:
    return f"GB-{transaction_id}"


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_payload(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None


def _float(value: Any) -> float | None:
    d = _decimal(value)
    return float(d) if d is not None else None


def _datetime(value: Any) -> dt | None:
    if isinstance(value, dt):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract_status(payload: dict[str, Any]) -> str:
    return str(payload.get("payment_status") or "").strip().lower()


def extract_order_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("order_id")
    return str(value).strip() if value not in (None, "") else None


def extract_invoice_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("invoice_id") or payload.get("iid")
    return str(value).strip() if value not in (None, "") else None


def extract_payment_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("payment_id")
    return str(value).strip() if value not in (None, "") else None


def _response_payload(payment: PaymentResponse) -> dict[str, Any]:
    return payment.model_dump(mode="json", exclude_none=True)


async def find_nowpayments_transaction(
    *,
    order_id: str | None = None,
    invoice_id: str | None = None,
    payment_id: str | None = None,
) -> Transaction | None:
    if order_id:
        try:
            return await Transaction.filter(id=int(order_id)).first()
        except (TypeError, ValueError):
            pass
    cp = None
    if payment_id:
        cp = await CryptoPayment.filter(
            provider=CryptoPayment.Provider.nowpayments,
            payment_id=str(payment_id),
        ).first()
    if not cp and invoice_id:
        cp = await CryptoPayment.filter(
            provider=CryptoPayment.Provider.nowpayments,
            invoice_id=str(invoice_id),
        ).first()
    if not cp:
        return None
    return await Transaction.filter(id=cp.transaction_id).first()


def _merge_extra(cp: CryptoPayment, payload: dict[str, Any], source: str) -> dict:
    extra = dict(cp.extra_data or {})
    key = "last_callback" if source == "callback" else "last_operation"
    extra[key] = _safe_payload(payload)
    extra["status_source"] = source
    extra["nowpayments_status"] = extract_status(payload)
    if pid := extract_payment_id(payload):
        extra["payment_id"] = pid
    if iid := extract_invoice_id(payload):
        extra["invoice_id"] = iid
    return extra


def _amount_mismatch(cp: CryptoPayment, payload: dict[str, Any]) -> bool:
    expected = _decimal(cp.price_amount)
    actual = _decimal(payload.get("price_amount"))
    if expected is None or actual is None:
        return False
    return abs(expected - actual) > Decimal("0.0001")


async def _alert_review_needed(
    transaction: Transaction, payload: dict[str, Any], reason: str
) -> None:
    from app.utils import reports

    payment_id = extract_payment_id(payload) or "-"
    invoice_id = extract_invoice_id(payload) or "-"
    reports.report(
        reports.ReportTopic.misc,
        "⚠️ پرداخت NowPayments نیاز به بررسی دستی دارد.\n"
        f"کد پیگیری: <code>{tracking_code(transaction.id)}</code>\n"
        f"فاکتور داخلی: <code>{transaction.id}</code>\n"
        f"Invoice: <code>{invoice_id}</code>\n"
        f"Payment: <code>{payment_id}</code>\n"
        f"علت: <b>{reason}</b>\n"
        "این پرداخت به‌صورت خودکار شارژ نشد.",
        legacy_super_users=True,
    )


def _apply_payment_fields(cp: CryptoPayment, payload: dict[str, Any]) -> None:
    cp.payment_id = extract_payment_id(payload) or cp.payment_id
    cp.pay_currency = payload.get("pay_currency") or cp.pay_currency
    if (pay_amount := _float(payload.get("pay_amount"))) is not None:
        cp.pay_amount = pay_amount
    if (outcome_amount := _float(payload.get("outcome_amount"))) is not None:
        cp.outcome_amount = outcome_amount
    cp.outcome_currency = payload.get("outcome_currency") or cp.outcome_currency
    cp.purchase_id = (
        str(payload.get("purchase_id"))
        if payload.get("purchase_id") not in (None, "")
        else cp.purchase_id
    )
    cp.pay_address = payload.get("pay_address") or cp.pay_address
    cp.fee = payload.get("fee") or cp.fee
    if updated_at := _datetime(payload.get("updated_at")):
        cp.nowpm_updated_at = updated_at


async def _mark_review(
    transaction: Transaction,
    cp: CryptoPayment,
    payload: dict[str, Any],
    *,
    source: str,
    reason: str,
) -> dict[str, str]:
    extra = _merge_extra(cp, payload, source)
    alert = not extra.get("review_alerted")
    extra["review_required"] = True
    extra["review_reason"] = reason
    extra["review_alerted"] = True
    _apply_payment_fields(cp, payload)
    cp.payment_status = CryptoPayment.PaymentStatus.partially_paid
    cp.extra_data = extra
    await cp.save()
    await Transaction.filter(id=transaction.id).update(
        status=Transaction.Status.partially_paid
    )
    if alert:
        await _alert_review_needed(transaction, payload, reason)
    return {"result": "review", "status": extract_status(payload)}


async def finalize_nowpayments_payment(
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
    if not cp or cp.provider != CryptoPayment.Provider.nowpayments:
        return {"result": "ignored", "status": status}

    extra = _merge_extra(cp, payload, source)
    if transaction.status == Transaction.Status.finished:
        cp.extra_data = extra
        _apply_payment_fields(cp, payload)
        await cp.save()
        return {"result": "already_finished", "status": status}

    if status == STATUS_FINISHED:
        if _amount_mismatch(cp, payload):
            return await _mark_review(
                transaction,
                cp,
                payload,
                source=source,
                reason="amount_mismatch",
            )

        async with in_transaction():
            await transaction.fetch_related("crypto_payment")
            cp = transaction.crypto_payment
            extra = _merge_extra(cp, payload, source)
            transaction.status = Transaction.Status.finished
            transaction.finished_at = dt.now()
            transaction.amount_paid = max(
                0, transaction.amount - transaction.amount_free_given
            )
            await transaction.save()
            cp.payment_status = CryptoPayment.PaymentStatus.finished
            _apply_payment_fields(cp, payload)
            cp.extra_data = extra
            await cp.save()

        title = settings.get_settings().payment_nowpayments.menu_title
        text = (
            f"✅ پرداخت شما از طریق {title} با موفقیت تایید شد.\n\n"
            f"کد پیگیری: <code>{tracking_code(transaction.id)}</code>\n"
            f"مبلغ شارژ: <b>{transaction.amount:,}</b> تومان"
        )
        msg = await bot.send_message(transaction.user_id, text)
        await transaction.fetch_related("crypto_payment")
        helpers.transaction_log(transaction=transaction, payment=transaction.crypto_payment)
        jobs.activate_service(transaction, msg)
        return {"result": "completed", "status": status}

    if status in PENDING_STATUSES:
        await Transaction.filter(id=transaction.id).update(
            status=Transaction.Status.confirming
            if status in {"confirming", "confirmed"}
            else Transaction.Status.waiting
        )
        _apply_payment_fields(cp, payload)
        cp.payment_status = CryptoPayment.PaymentStatus.confirming
        cp.extra_data = extra
        await cp.save()
        return {"result": "pending", "status": status}

    if status in SENDING_STATUSES:
        await Transaction.filter(id=transaction.id).update(status=Transaction.Status.sending)
        _apply_payment_fields(cp, payload)
        cp.payment_status = CryptoPayment.PaymentStatus.sending
        cp.extra_data = extra
        await cp.save()
        return {"result": "pending", "status": status}

    if status in REVIEW_STATUSES:
        return await _mark_review(
            transaction,
            cp,
            payload,
            source=source,
            reason=status,
        )

    if status in FAILED_STATUSES:
        tx_status = (
            Transaction.Status.canceled
            if status in {"expired", "refunded"}
            else Transaction.Status.failed
        )
        cp_status = (
            CryptoPayment.PaymentStatus.expired
            if status == "expired"
            else CryptoPayment.PaymentStatus.failed
        )
        await Transaction.filter(id=transaction.id).update(status=tx_status)
        _apply_payment_fields(cp, payload)
        cp.payment_status = cp_status
        cp.extra_data = extra
        await cp.save()
        return {"result": "failed", "status": status}

    cp.extra_data = extra
    _apply_payment_fields(cp, payload)
    await cp.save()
    return {"result": "unknown", "status": status}


def _pick_best_payment(payments: list[PaymentResponse]) -> PaymentResponse | None:
    if not payments:
        return None
    priority = {
        "finished": 0,
        "sending": 1,
        "confirmed": 2,
        "confirming": 3,
        "waiting": 4,
        "partially_paid": 5,
        "expired": 6,
        "failed": 7,
        "refunded": 8,
    }
    return sorted(
        payments,
        key=lambda p: (
            priority.get(str(p.payment_status).lower(), 99),
            str(p.updated_at or p.created_at or ""),
        ),
    )[0]


async def check_nowpayments_transaction(
    transaction: Transaction,
    *,
    source: str,
) -> dict[str, str]:
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.nowpayments:
        return {"result": "ignored", "status": ""}
    payment: PaymentResponse | None = None
    if cp.payment_id:
        payment = await NowPaymentsAPI.get_payment_status(cp.payment_id)
    elif cp.invoice_id:
        payment = _pick_best_payment(
            await NowPaymentsAPI.get_payments(invoice_id=cp.invoice_id)
        )
    if not payment:
        return {"result": "no_payment", "status": ""}
    return await finalize_nowpayments_payment(
        transaction,
        _response_payload(payment),
        source=source,
    )


async def manual_approve_nowpayments_payment(
    transaction: Transaction,
    *,
    source: str,
    actor_id: int | None = None,
) -> str:
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    if not cp or cp.provider != CryptoPayment.Provider.nowpayments:
        return "ignored"
    if transaction.status == Transaction.Status.finished:
        return "already_finished"

    async with in_transaction():
        await transaction.fetch_related("crypto_payment")
        cp = transaction.crypto_payment
        transaction.status = Transaction.Status.finished
        transaction.finished_at = dt.now()
        transaction.amount_paid = max(0, transaction.amount - transaction.amount_free_given)
        await transaction.save()
        cp.payment_status = CryptoPayment.PaymentStatus.finished
        extra = dict(cp.extra_data or {})
        extra.update(
            {
                "manual_approved": True,
                "manual_approved_at": dt.now().isoformat(),
                "manual_approved_by": actor_id,
                "status_source": source,
                "nowpayments_status": "manual_approved",
            }
        )
        cp.extra_data = extra
        await cp.save()

    title = settings.get_settings().payment_nowpayments.menu_title
    msg = await bot.send_message(
        transaction.user_id,
        f"✅ پرداخت شما از طریق {title} به‌صورت دستی تایید شد.\n\n"
        f"کد پیگیری: <code>{tracking_code(transaction.id)}</code>\n"
        f"مبلغ شارژ: <b>{transaction.amount:,}</b> تومان",
    )
    await transaction.fetch_related("crypto_payment")
    helpers.transaction_log(transaction=transaction, payment=transaction.crypto_payment)
    jobs.activate_service(transaction, msg)
    return "approved"


async def process_nowpayments_review_queue() -> None:
    for _ in range(50):
        raw = await redis.lpop(NOWPAYMENTS_REVIEW_QUEUE)
        if not raw:
            return
        try:
            item = json.loads(raw)
            transaction_id = int(item["transaction_id"])
        except Exception:  # noqa: BLE001
            continue
        transaction = await Transaction.filter(id=transaction_id).first()
        if not transaction:
            continue
        action = str(item.get("action") or "check")
        actor_id = item.get("actor_id")
        try:
            if action == "approve":
                await manual_approve_nowpayments_payment(
                    transaction,
                    source="web_manual_approve",
                    actor_id=actor_id,
                )
            else:
                await check_nowpayments_transaction(transaction, source="web_check")
        except NowPaymentsError as exc:
            logger.warning("nowpayments queued %s failed for tx=%s: %s", action, transaction_id, exc)


async def auto_check_nowpayments_payments(limit: int = 10) -> None:
    st = settings.get_settings().payment_nowpayments
    if not st.enabled or not st.api_key:
        return
    rows = (
        await CryptoPayment.filter(
            provider=CryptoPayment.Provider.nowpayments,
            transaction__status__in=[
                Transaction.Status.waiting,
                Transaction.Status.confirming,
                Transaction.Status.sending,
            ],
        )
        .prefetch_related("transaction")
        .order_by("created_at")
        .limit(limit)
    )
    for cp in rows:
        tx = cp.transaction
        marker = cp.payment_id or cp.invoice_id or tx.id
        key = f"nowpayments:auto-check:{marker}"
        try:
            if await redis.get(key):
                continue
            await redis.set(key, "1", ex=60)
            await check_nowpayments_transaction(tx, source="auto_check")
        except NowPaymentsError as exc:
            logger.debug("nowpayments auto-check failed tx=%s: %s", tx.id, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("nowpayments auto-check unexpected failure tx=%s: %s", tx.id, exc)
