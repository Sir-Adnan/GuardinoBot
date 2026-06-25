"""Dashboard summary (admin+). Mirrors the bot's stats panel as JSON."""

from datetime import datetime as dt
from datetime import timedelta as td

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.api.schemas import DashboardOut
from app.models.proxy import Proxy
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardOut)
async def summary(_: User = Depends(require_role(User.Role.admin))) -> DashboardOut:
    now = dt.now()
    day_ago = now - td(days=1)
    month_ago = now - td(days=30)
    return DashboardOut(
        users_total=await User.all().count(),
        users_today=await User.filter(created_at__gt=day_ago).count(),
        users_month=await User.filter(created_at__gt=month_ago).count(),
        proxies_total=await Proxy.all().count(),
        proxies_active=await Proxy.filter(status="active").count(),
        blocked_users=await User.filter(is_blocked=True).count(),
    )
