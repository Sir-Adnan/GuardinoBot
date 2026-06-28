"""Transactions (payments). Reseller-scoped list + super-admin payment actions."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.expressions import Q

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import OkOut, TransactionListItem, TransactionsPage
from app.models.user import CryptoPayment, Transaction, User
from app.utils.audit import record_audit

router = APIRouter(prefix="/transactions", tags=["transactions"])
PLISIO_REVIEW_QUEUE = "plisio:review:queue"
NOWPAYMENTS_REVIEW_QUEUE = "nowpayments:review:queue"

TYPE_NAMES = {
    1: "crypto",
    2: "card_to_card",
    3: "perfectmoney",
    4: "rial_gateway",
    5: "by_admin",
    6: "gift",
    7: "tronseller",
}
STATUS_NAMES = {
    1: "waiting",
    2: "failed",
    3: "canceled",
    4: "partially_paid",
    5: "finished",
    6: "rejected",
    7: "sending",
    8: "confirming",
}


def _scope(viewer: User):
    q = Transaction.all()
    if viewer.role < User.Role.admin:
        q = q.filter(user__parent_id=viewer.id)
    return q


def _item(tx: Transaction) -> TransactionListItem:
    ty, st = int(tx.type), int(tx.status)
    provider = None
    provider_txn_id = None
    invoice_url = None
    pay_currency = None
    pay_amount = None
    provider_status = None
    tracking_code = None
    invoice_currency = None
    invoice_amount = None
    allowed_currencies: list[str] = []
    cp = getattr(tx, "crypto_payment", None)
    if ty == int(Transaction.PaymentType.crypto) and isinstance(cp, CryptoPayment):
        extra = cp.extra_data if isinstance(cp.extra_data, dict) else {}
        provider = getattr(cp.provider, "value", str(cp.provider))
        provider_txn_id = cp.payment_id or cp.invoice_id or cp.purchase_id
        tracking_code = extra.get("tracking_code") or cp.order_description or f"GB-{tx.id}"
        invoice_url = extra.get("invoice_url")
        pay_currency = cp.pay_currency or cp.price_currency
        pay_amount = cp.pay_amount or cp.price_amount
        invoice_currency = extra.get("invoice_currency") or cp.price_currency
        invoice_amount = extra.get("payable_usdt") or str(cp.price_amount or "")
        allowed_currencies = extra.get("allowed_currencies") or []
        provider_status = extra.get("plisio_status") or extra.get("nowpayments_status") or getattr(
            cp.payment_status, "name", str(cp.payment_status)
        )
    u = getattr(tx, "user", None)
    return TransactionListItem(
        id=tx.id,
        type=ty,
        type_name=TYPE_NAMES.get(ty, str(ty)),
        status=st,
        status_name=STATUS_NAMES.get(st, str(st)),
        amount=tx.amount or 0,
        amount_free_given=tx.amount_free_given or 0,
        amount_paid=tx.amount_paid,
        user_id=tx.user_id,
        provider=provider,
        provider_txn_id=provider_txn_id,
        tracking_code=tracking_code,
        invoice_url=invoice_url,
        pay_currency=pay_currency,
        pay_amount=pay_amount,
        provider_status=provider_status,
        invoice_currency=invoice_currency,
        invoice_amount=invoice_amount,
        allowed_currencies=allowed_currencies if isinstance(allowed_currencies, list) else [],
        user_name=getattr(u, "name", None),
        username=getattr(u, "username", None),
        created_at=tx.created_at,
        finished_at=tx.finished_at,
    )


@router.get("", response_model=TransactionsPage)
async def list_transactions(
    viewer: User = Depends(require_role(User.Role.reseller)),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = None,
    status_filter: Optional[int] = Query(None, alias="status"),
    type_filter: Optional[int] = Query(None, alias="type"),
    provider: Optional[str] = None,
    provider_status: Optional[str] = None,
    search: Optional[str] = None,
) -> TransactionsPage:
    q = _scope(viewer)
    if user_id:
        q = q.filter(user_id=user_id)
    if status_filter:
        q = q.filter(status=status_filter)
    if type_filter:
        q = q.filter(type=type_filter)
    if provider:
        q = q.filter(crypto_payment__provider=str(provider).strip())
    if provider_status:
        for st in CryptoPayment.PaymentStatus:
            if st.name == provider_status:
                q = q.filter(crypto_payment__payment_status=st)
                break
    if search:
        s = search.strip()
        if s:
            parts = [
                Q(user__username__icontains=s),
                Q(user__name__icontains=s),
                Q(crypto_payment__invoice_id__icontains=s),
                Q(crypto_payment__payment_id__icontains=s),
                Q(crypto_payment__order_id__icontains=s),
                Q(crypto_payment__order_description__icontains=s),
                Q(crypto_payment__purchase_id__icontains=s),
                Q(crypto_payment__pay_address__icontains=s),
            ]
            if s.upper().startswith("GB-"):
                try:
                    parts.append(Q(id=int(s[3:])))
                except ValueError:
                    pass
            elif s.isdigit():
                n = int(s)
                parts.extend([Q(id=n), Q(user_id=n)])
            expr = parts[0]
            for part in parts[1:]:
                expr |= part
            q = q.filter(expr)
    total = await q.count()
    rows = await (
        q.prefetch_related("crypto_payment", "user")
        .order_by("-created_at")
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return TransactionsPage(items=[_item(t) for t in rows], total=total)


async def _get_crypto_transaction(tx_id: int, provider: CryptoPayment.Provider) -> Transaction:
    tx = await (
        Transaction.filter(id=tx_id)
        .prefetch_related("crypto_payment")
        .first()
    )
    cp = getattr(tx, "crypto_payment", None) if tx else None
    if not tx or not isinstance(cp, CryptoPayment) or cp.provider != provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{provider.value} transaction not found")
    return tx


async def _queue_crypto_action(
    tx_id: int,
    provider: CryptoPayment.Provider,
    queue: str,
    action: str,
    actor: User,
) -> OkOut:
    await _get_crypto_transaction(tx_id, provider)
    await redis.rpush(
        queue,
        json.dumps({"transaction_id": tx_id, "action": action, "actor_id": actor.id}),
    )
    await record_audit(
        action=f"{provider.value}_payment.{action}",
        actor=actor,
        target_type="transaction",
        target_id=str(tx_id),
        detail={"queued": True},
    )
    return OkOut(ok=True, status="queued")


@router.post("/{tx_id}/plisio/check", response_model=OkOut)
async def check_plisio_transaction(
    tx_id: int,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    return await _queue_crypto_action(
        tx_id, CryptoPayment.Provider.plisio, PLISIO_REVIEW_QUEUE, "check", actor
    )


@router.post("/{tx_id}/plisio/manual-approve", response_model=OkOut)
async def manual_approve_plisio_transaction(
    tx_id: int,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    tx = await _get_crypto_transaction(tx_id, CryptoPayment.Provider.plisio)
    if tx.status == Transaction.Status.finished:
        return OkOut(ok=True, status="already_finished")
    return await _queue_crypto_action(
        tx_id, CryptoPayment.Provider.plisio, PLISIO_REVIEW_QUEUE, "approve", actor
    )


@router.post("/{tx_id}/nowpayments/check", response_model=OkOut)
async def check_nowpayments_transaction(
    tx_id: int,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    return await _queue_crypto_action(
        tx_id,
        CryptoPayment.Provider.nowpayments,
        NOWPAYMENTS_REVIEW_QUEUE,
        "check",
        actor,
    )


@router.post("/{tx_id}/nowpayments/manual-approve", response_model=OkOut)
async def manual_approve_nowpayments_transaction(
    tx_id: int,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    tx = await _get_crypto_transaction(tx_id, CryptoPayment.Provider.nowpayments)
    if tx.status == Transaction.Status.finished:
        return OkOut(ok=True, status="already_finished")
    return await _queue_crypto_action(
        tx_id,
        CryptoPayment.Provider.nowpayments,
        NOWPAYMENTS_REVIEW_QUEUE,
        "approve",
        actor,
    )
