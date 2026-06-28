"""Transactions (payments). Reseller-scoped to their own subtree. Read-only."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.api.schemas import TransactionListItem, TransactionsPage
from app.models.user import CryptoPayment, Transaction, User

router = APIRouter(prefix="/transactions", tags=["transactions"])

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
    cp = getattr(tx, "crypto_payment", None)
    if ty == int(Transaction.PaymentType.crypto) and isinstance(cp, CryptoPayment):
        extra = cp.extra_data if isinstance(cp.extra_data, dict) else {}
        provider = getattr(cp.provider, "value", str(cp.provider))
        provider_txn_id = cp.payment_id or cp.invoice_id
        invoice_url = extra.get("invoice_url")
        pay_currency = cp.pay_currency or cp.price_currency
        pay_amount = cp.pay_amount or cp.price_amount
        provider_status = extra.get("plisio_status") or getattr(
            cp.payment_status, "name", str(cp.payment_status)
        )
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
        invoice_url=invoice_url,
        pay_currency=pay_currency,
        pay_amount=pay_amount,
        provider_status=provider_status,
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
) -> TransactionsPage:
    q = _scope(viewer)
    if user_id:
        q = q.filter(user_id=user_id)
    if status_filter:
        q = q.filter(status=status_filter)
    if type_filter:
        q = q.filter(type=type_filter)
    total = await q.count()
    rows = await (
        q.prefetch_related("crypto_payment")
        .order_by("-created_at")
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return TransactionsPage(items=[_item(t) for t in rows], total=total)
