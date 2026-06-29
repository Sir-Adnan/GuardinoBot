"""Dashboard summary (admin+). Mirrors the bot's stats panel as JSON."""

import asyncio
from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from fastapi import APIRouter, Depends
from tortoise.functions import Sum

from app.api.deps import require_role
from app.api.schemas import (
    DashboardOut,
    PanelHealthItem,
    PanelHealthOut,
    PeriodStat,
)
from app.models.proxy import Proxy
from app.models.server import Server
from app.models.setting import BotSetting
from app.models.user import Invoice, Transaction, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_GB = 1024**3
# fallbacks mirror app/utils/settings.py defaults (the bot owns the real values)
_WARN_DEFAULT = 1_000_000
_CRITICAL_DEFAULT = 500_000
# Match the panel client's own request timeout (pasarguard/marzban use 15s) so a
# slow-but-healthy panel isn't falsely flagged "unreachable". Panels are pinged
# concurrently, so this is the worst-case wait for one dead panel, not the sum.
_PING_TIMEOUT = 15  # seconds per panel call


async def _sum(queryset, field: str = "amount") -> int:
    rows = await queryset.annotate(s=Sum(field)).values("s")
    return int((rows[0]["s"] if rows else 0) or 0)


async def _gb_sold(queryset) -> float:
    """GB provisioned by the matched subscriptions (Σ service.data_limit).

    Summed in Python from the joined values: a DB ``Sum`` over the ``service``
    FK join can be split by the implicit GROUP BY and undercount.
    """
    vals = await queryset.values_list("service__data_limit", flat=True)
    return round(sum(int(v) for v in vals if v) / _GB, 1)


async def _period(since) -> PeriodStat:
    """income / sales / orders / GB-sold since a given datetime (to now)."""
    fin = Transaction.Status.finished
    return PeriodStat(
        income=await _sum(Transaction.filter(status=fin, created_at__gt=since), "amount_paid"),
        sales=await _sum(Invoice.filter(is_draft=False, created_at__gt=since)),
        orders=await Proxy.filter(created_at__gt=since).count(),
        gb=await _gb_sold(Proxy.filter(created_at__gt=since)),
    )


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
        total_sales=await _sum(Invoice.filter(is_draft=False)),
        total_income=await _sum(Transaction.filter(status=fin), "amount_paid"),
        active_users=await User.filter(proxies__status="active").distinct().count(),
        resellers_total=await User.filter(role__gte=User.Role.reseller).count(),
        period_today=await _period(day_ago),
        period_week=await _period(now - td(days=7)),
        period_month=await _period(month_ago),
    )


async def _read_int(key: str, default: int) -> int:
    rows = await BotSetting.filter(_key=key).values("_value")
    try:
        v = int((rows[0]["_value"] if rows else default) or default)
        return v
    except (ValueError, TypeError):
        return default


async def _check_panel(server: Server, warn: int, critical: int) -> PanelHealthItem:
    """Live-ping one panel (admin + Guardino balance) with a timeout. Errors are
    reduced to non-sensitive codes so no panel credentials/URLs leak."""
    ptype = str(getattr(server.panel_type, "value", server.panel_type or "marzban"))
    base = {"id": server.id, "name": server.identifier, "panel_type": ptype}
    # local import (mirrors proxies.py) — app.panels never imports app.main
    from app.panels.base import PanelAuthError, PanelError
    from app.panels.registry import build_panel

    try:
        panel = build_panel(server)
    except Exception:  # noqa: BLE001 - bad/incomplete server row
        return PanelHealthItem(**base, ok=False, error="error")

    try:
        admin = await asyncio.wait_for(panel.get_admin(), timeout=_PING_TIMEOUT)
    except PanelAuthError:
        return PanelHealthItem(**base, ok=False, error="auth")
    except (PanelError, asyncio.TimeoutError):
        return PanelHealthItem(**base, ok=False, error="unreachable")
    except Exception:  # noqa: BLE001
        return PanelHealthItem(**base, ok=False, error="error")

    balance = level = None
    if getattr(panel, "panel_managed_billing", False):
        try:
            balance = await asyncio.wait_for(panel.get_balance(), timeout=_PING_TIMEOUT)
            level = (
                "critical" if balance < critical
                else ("warn" if balance < warn else "ok")
            )
        except Exception:  # noqa: BLE001 - balance is best-effort
            balance = level = None

    return PanelHealthItem(
        **base, ok=True, admin=admin.username, balance=balance, balance_level=level
    )


@router.get("/panel-health", response_model=PanelHealthOut)
async def panel_health(
    _: User = Depends(require_role(User.Role.admin)),
) -> PanelHealthOut:
    """Live reachability + Guardino balance per enabled panel. Lazy (the widget
    calls it on demand) since it makes one network call per panel."""
    warn = await _read_int("guardino_balance_warn", _WARN_DEFAULT)
    critical = await _read_int("guardino_balance_critical", _CRITICAL_DEFAULT)
    servers = await Server.filter(is_enabled=True).all()
    items = await asyncio.gather(*(_check_panel(s, warn, critical) for s in servers))
    return PanelHealthOut(
        items=list(items),
        checked_at=dt.now(UTC).isoformat(timespec="seconds"),
        warn=warn,
        critical=critical,
    )
