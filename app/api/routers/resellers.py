"""Resellers (users with role >= reseller). Admin+ only.

Balance is computed per row (User.get_balance) — fine for an admin list; the
page size is capped low.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.expressions import Q

from app.api.deps import require_role
from app.api.schemas import (
    ROLE_NAMES,
    ResellerDetail,
    ResellerListItem,
    ResellersPage,
)
from app.models.user import User

router = APIRouter(prefix="/resellers", tags=["resellers"])


async def _item(u: User) -> ResellerListItem:
    return ResellerListItem(
        id=u.id,
        username=u.username,
        name=u.name,
        role=int(u.role),
        role_name=ROLE_NAMES.get(int(u.role), str(int(u.role))),
        balance=await u.get_balance(),
        children_count=await User.filter(parent_id=u.id).count(),
        is_postpaid=u.is_postpaid,
        is_blocked=u.is_blocked,
        created_at=u.created_at,
    )


@router.get("", response_model=ResellersPage)
async def list_resellers(
    _: User = Depends(require_role(User.Role.admin)),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    search: Optional[str] = None,
) -> ResellersPage:
    q = User.filter(role__gte=User.Role.reseller)
    if search:
        s = search.strip().lstrip("@")
        cond = Q(username__icontains=s) | Q(name__icontains=s)
        if s.isdigit():
            cond = cond | Q(id=int(s))
        q = q.filter(cond)
    total = await q.count()
    rows = await q.order_by("-created_at").offset((page - 1) * per_page).limit(per_page)
    items = [await _item(u) for u in rows]
    return ResellersPage(items=items, total=total)


@router.get("/{reseller_id}", response_model=ResellerDetail)
async def get_reseller(
    reseller_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ResellerDetail:
    u = await User.filter(id=reseller_id, role__gte=User.Role.reseller).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reseller not found")
    balance = await u.get_balance()
    return ResellerDetail(
        id=u.id,
        username=u.username,
        name=u.name,
        role=int(u.role),
        role_name=ROLE_NAMES.get(int(u.role), str(int(u.role))),
        balance=balance,
        children_count=await User.filter(parent_id=u.id).count(),
        is_postpaid=u.is_postpaid,
        is_blocked=u.is_blocked,
        created_at=u.created_at,
        available_credit=await u.get_available_credit(balance),
        max_post_paid_credit=u.max_post_paid_credit,
        proxies_count=await u.proxies.all().count(),
        parent_id=u.parent_id,
    )
