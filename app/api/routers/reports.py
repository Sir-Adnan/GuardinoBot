"""Sales / revenue reports (admin+). Read-only aggregations.

Totals use the safe Sum-into-values pattern (same as User.get_balance); the
per-day series is bucketed in Python to avoid DB-specific date SQL; the payment
breakdown loops the known payment types (simple filters, no group_by surprises).
"""

from datetime import datetime as dt
from datetime import timedelta as td
from typing import Optional

from fastapi import APIRouter, Depends, Query
from tortoise.functions import Sum

from app.api.deps import require_role
from app.api.schemas import (
    PaymentBreakdownItem,
    ReportPoint,
    ReportsOut,
    TopBuyerItem,
    TopServiceItem,
)
from app.models.proxy import Proxy, ProxyStatus
from app.models.service import Service
from app.models.user import Invoice, Transaction, User

_GB = 1024**3

router = APIRouter(prefix="/reports", tags=["reports"])

TYPE_NAMES = {
    1: "crypto",
    2: "card_to_card",
    3: "perfectmoney",
    4: "rial_gateway",
    5: "by_admin",
    6: "gift",
    7: "tronseller",
}


async def _sum(queryset, field: str = "amount") -> int:
    rows = await queryset.annotate(s=Sum(field)).values("s")
    return int((rows[0]["s"] if rows else 0) or 0)


async def _gb(queryset) -> float:
    """GB provisioned by the matched subscriptions (Σ of their service.data_limit).

    Summed in Python from the joined values — a DB ``Sum`` over the ``service``
    FK join can be split into partial rows by the implicit GROUP BY and silently
    undercount, so we pull the per-proxy values and add them up exactly.
    """
    vals = await queryset.values_list("service__data_limit", flat=True)
    bytes_total = sum(int(v) for v in vals if v)
    return round(bytes_total / _GB, 2)


def _parse_date(s: Optional[str]):
    if not s:
        return None
    try:
        return dt.fromisoformat(s)
    except ValueError:
        return None


@router.get("/summary", response_model=ReportsOut)
async def summary(
    _: User = Depends(require_role(User.Role.admin)),
    days: int = Query(30, ge=1, le=365),
    start: Optional[str] = None,  # ISO date; overrides `days` when given
    end: Optional[str] = None,
) -> ReportsOut:
    now = dt.now()
    start_dt = _parse_date(start)
    if start_dt is not None:
        since = start_dt
        end_dt = _parse_date(end)
        # date-only end → include the whole day
        until = (end_dt + td(days=1)) if end_dt else now
        days = max(1, (until - since).days)
    else:
        since = now - td(days=days)
        until = now

    def _rng(q):
        return q.filter(created_at__gte=since, created_at__lt=until)

    sales_total = await _sum(_rng(Invoice.filter(is_draft=False)))
    income_total = await _sum(
        _rng(Transaction.filter(status=Transaction.Status.finished)), "amount_paid"
    )
    orders = await _rng(Proxy.all()).count()
    new_users = await _rng(User.all()).count()
    total_tx = await _rng(Transaction.all()).count()
    finished_tx = await _rng(
        Transaction.filter(status=Transaction.Status.finished)
    ).count()
    failed_payments = max(0, total_tx - finished_tx)
    gb_sold = await _gb(_rng(Proxy.all()))

    # all-time (lifetime) totals — ignore the selected range
    all_sales_total = await _sum(Invoice.filter(is_draft=False))
    all_income_total = await _sum(
        Transaction.filter(status=Transaction.Status.finished), "amount_paid"
    )
    all_users = await User.all().count()
    all_gb_sold = await _gb(Proxy.all())

    # subscription (proxy) stats — current state
    proxies_by_status: dict[str, int] = {}
    for st in ProxyStatus:
        proxies_by_status[st.value] = await Proxy.filter(status=st).count()
    proxies_total = sum(proxies_by_status.values())
    proxies_active = proxies_by_status.get(ProxyStatus.active.value, 0)

    # per-day revenue series (capped at 60 points), bucketed in Python
    series_days = min(days, 60)
    series_since = until - td(days=series_days)
    inv_rows = await Invoice.filter(
        is_draft=False, created_at__gte=series_since, created_at__lt=until
    ).values("created_at", "amount")
    buckets: dict[str, int] = {}
    for r in inv_rows:
        d = r["created_at"]
        key = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        buckets[key] = buckets.get(key, 0) + int(r["amount"] or 0)
    anchor = until - td(seconds=1)  # last inclusive instant of the range
    series = [
        ReportPoint(
            date=(anchor - td(days=i)).strftime("%Y-%m-%d"),
            amount=buckets.get((anchor - td(days=i)).strftime("%Y-%m-%d"), 0),
        )
        for i in range(series_days, -1, -1)
    ]

    # payment breakdown by type (finished only)
    breakdown: list[PaymentBreakdownItem] = []
    for ty, name in TYPE_NAMES.items():
        base = _rng(
            Transaction.filter(status=Transaction.Status.finished, type=ty)
        )
        count = await base.count()
        if count == 0:
            continue
        breakdown.append(
            PaymentBreakdownItem(
                type=ty,
                type_name=name,
                count=count,
                amount=await _sum(base, "amount_paid"),
            )
        )

    # top services — FULL list, range-aware: orders (non-draft invoices) +
    # revenue per service inside the selected range, sorted by revenue.
    # Aggregated in Python (values pull) to dodge FK-join GROUP BY surprises.
    svc_rows = await _rng(
        Invoice.filter(is_draft=False, service_id__not_isnull=True)
    ).values("service_id", "amount")
    svc_agg: dict[int, dict[str, int]] = {}
    for r in svc_rows:
        sid = int(r["service_id"])
        a = svc_agg.setdefault(sid, {"count": 0, "revenue": 0})
        a["count"] += 1
        a["revenue"] += int(r["amount"] or 0)
    svc_names = dict(
        await Service.filter(id__in=list(svc_agg)).values_list("id", "name")
    ) if svc_agg else {}
    top_services = sorted(
        (
            TopServiceItem(
                id=sid,
                name=svc_names.get(sid, f"#{sid}"),
                count=a["count"],
                revenue=a["revenue"],
            )
            for sid, a in svc_agg.items()
        ),
        key=lambda x: (-x.revenue, -x.count),
    )

    # orders split by invoice type (purchase / renew_now / renew_reserve)
    _ORDER_TYPES = {
        int(Invoice.Type.purchase): "purchase",
        int(Invoice.Type.renew_now): "renew_now",
        int(Invoice.Type.renew_reserve): "renew_reserve",
    }
    orders_by_type: list[PaymentBreakdownItem] = []
    for ty, name in _ORDER_TYPES.items():
        base = _rng(Invoice.filter(is_draft=False, type=ty))
        count = await base.count()
        if count == 0:
            continue
        orders_by_type.append(
            PaymentBreakdownItem(
                type=ty, type_name=name, count=count, amount=await _sum(base)
            )
        )

    # top buyers by spend (non-draft invoices) inside the range
    buyer_rows = await _rng(Invoice.filter(is_draft=False)).values(
        "user_id", "amount"
    )
    buyer_agg: dict[int, dict[str, int]] = {}
    for r in buyer_rows:
        uid = int(r["user_id"])
        a = buyer_agg.setdefault(uid, {"orders": 0, "amount": 0})
        a["orders"] += 1
        a["amount"] += int(r["amount"] or 0)
    buyer_ids = sorted(buyer_agg, key=lambda u: -buyer_agg[u]["amount"])[:10]
    buyer_users = {
        u["id"]: u
        for u in await User.filter(id__in=buyer_ids).values("id", "name", "username")
    } if buyer_ids else {}
    top_buyers = [
        TopBuyerItem(
            user_id=uid,
            name=(buyer_users.get(uid) or {}).get("name"),
            username=(buyer_users.get(uid) or {}).get("username"),
            orders=buyer_agg[uid]["orders"],
            amount=buyer_agg[uid]["amount"],
        )
        for uid in buyer_ids
    ]

    return ReportsOut(
        days=days,
        start=since.strftime("%Y-%m-%d"),
        end=(until - td(seconds=1)).strftime("%Y-%m-%d"),
        sales_total=sales_total,
        income_total=income_total,
        orders=orders,
        new_users=new_users,
        failed_payments=failed_payments,
        gb_sold=gb_sold,
        all_sales_total=all_sales_total,
        all_income_total=all_income_total,
        all_orders=proxies_total,
        all_users=all_users,
        all_gb_sold=all_gb_sold,
        proxies_total=proxies_total,
        proxies_active=proxies_active,
        proxies_by_status=proxies_by_status,
        total_transactions=total_tx,
        revenue_series=series,
        payment_breakdown=breakdown,
        top_services=top_services,
        orders_by_type=orders_by_type,
        top_buyers=top_buyers,
    )
