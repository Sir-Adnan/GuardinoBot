"""Dashboard summary (admin+). Mirrors the bot's stats panel as JSON."""

from datetime import datetime as dt
from datetime import timedelta as td

from fastapi import APIRouter, Depends
from tortoise.functions import Sum

from app.api.deps import require_role
from app.api.schemas import DashboardOut
from app.models.proxy import Proxy
from app.models.server import Server
from app.models.user import Invoice, Transaction, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _sum(queryset, field: str = "amount") -> int:
    rows = await queryset.annotate(s=Sum(field)).values("s")
    return int((rows[0]["s"] if rows else 0) or 0)


@router.get("/summary", response_model=DashboardOut)
async def summary(_: User = Depends(require_role(User.Role.admin))) -> DashboardOut:
    now = dt.now()
    day_ago = now - td(days=1)
    month_ago = now - td(days=30)
    fin = Transaction.Status.finished

    # last-14-days invoice totals (oldest → newest), bucketed in Python
    inv_rows = await Invoice.filter(
        is_draft=False, created_at__gte=now - td(days=14)
    ).values("created_at", "amount")
    buckets: dict[str, int] = {}
    for r in inv_rows:
        c = r["created_at"]
        key = c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)[:10]
        buckets[key] = buckets.get(key, 0) + int(r["amount"] or 0)
    spark = [
        buckets.get((now - td(days=i)).strftime("%Y-%m-%d"), 0)
        for i in range(13, -1, -1)
    ]

    return DashboardOut(
        users_total=await User.all().count(),
        users_today=await User.filter(created_at__gt=day_ago).count(),
        users_month=await User.filter(created_at__gt=month_ago).count(),
        proxies_total=await Proxy.all().count(),
        proxies_active=await Proxy.filter(status="active").count(),
        blocked_users=await User.filter(is_blocked=True).count(),
        today_sales=await _sum(Invoice.filter(is_draft=False, created_at__gt=day_ago)),
        today_income=await _sum(
            Transaction.filter(status=fin, created_at__gt=day_ago), "amount_paid"
        ),
        month_sales=await _sum(Invoice.filter(is_draft=False, created_at__gt=month_ago)),
        month_income=await _sum(
            Transaction.filter(status=fin, created_at__gt=month_ago), "amount_paid"
        ),
        servers_total=await Server.all().count(),
        servers_enabled=await Server.filter(is_enabled=True).count(),
        pending_payments=await Transaction.filter(created_at__gt=month_ago)
        .exclude(status=fin)
        .count(),
        orders_today=await Proxy.filter(created_at__gt=day_ago).count(),
        revenue_spark=spark,
    )
