"""Sales / revenue reports (admin+). Read-only aggregations.

Totals use the safe Sum-into-values pattern (same as User.get_balance); the
per-day series is bucketed in Python to avoid DB-specific date SQL; the payment
breakdown loops the known payment types (simple filters, no group_by surprises).
"""

from datetime import datetime as dt
from datetime import timedelta as td

from fastapi import APIRouter, Depends, Query
from tortoise.functions import Count, Sum

from app.api.deps import require_role
from app.api.schemas import (
    PaymentBreakdownItem,
    ReportPoint,
    ReportsOut,
    TopServiceItem,
)
from app.models.proxy import Proxy
from app.models.service import Service
from app.models.user import Invoice, Transaction, User

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


@router.get("/summary", response_model=ReportsOut)
async def summary(
    _: User = Depends(require_role(User.Role.admin)),
    days: int = Query(30, ge=1, le=365),
) -> ReportsOut:
    now = dt.now()
    since = now - td(days=days)

    sales_total = await _sum(Invoice.filter(is_draft=False, created_at__gte=since))
    income_total = await _sum(
        Transaction.filter(status=Transaction.Status.finished, created_at__gte=since),
        "amount_paid",
    )
    orders = await Proxy.filter(created_at__gte=since).count()
    new_users = await User.filter(created_at__gte=since).count()

    # per-day revenue series (capped at 30 points), bucketed in Python
    series_days = min(days, 30)
    series_since = now - td(days=series_days)
    inv_rows = await Invoice.filter(
        is_draft=False, created_at__gte=series_since
    ).values("created_at", "amount")
    buckets: dict[str, int] = {}
    for r in inv_rows:
        d = r["created_at"]
        key = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        buckets[key] = buckets.get(key, 0) + int(r["amount"] or 0)
    series = [
        ReportPoint(
            date=(now - td(days=i)).strftime("%Y-%m-%d"),
            amount=buckets.get((now - td(days=i)).strftime("%Y-%m-%d"), 0),
        )
        for i in range(series_days, -1, -1)
    ]

    # payment breakdown by type (finished only)
    breakdown: list[PaymentBreakdownItem] = []
    for ty, name in TYPE_NAMES.items():
        base = Transaction.filter(
            status=Transaction.Status.finished, type=ty, created_at__gte=since
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

    # top services by subscription count (all-time)
    top = (
        await Service.annotate(num=Count("proxies"))
        .order_by("-num")
        .limit(8)
        .values("id", "name", "num")
    )
    top_services = [
        TopServiceItem(id=t["id"], name=t["name"], count=int(t["num"] or 0))
        for t in top
        if int(t["num"] or 0) > 0
    ]

    return ReportsOut(
        days=days,
        sales_total=sales_total,
        income_total=income_total,
        orders=orders,
        new_users=new_users,
        revenue_series=series,
        payment_breakdown=breakdown,
        top_services=top_services,
    )
