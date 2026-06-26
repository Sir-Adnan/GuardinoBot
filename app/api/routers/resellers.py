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
    OkOut,
    PromoteResellerIn,
    ResellerDetail,
    ResellerListItem,
    ResellersPage,
    UserListItem,
    UsersPage,
)
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/resellers", tags=["resellers"])


def _user_item(u: User) -> UserListItem:
    return UserListItem(
        id=u.id,
        username=u.username,
        name=u.name,
        role=int(u.role),
        role_name=ROLE_NAMES.get(int(u.role), str(int(u.role))),
        is_blocked=u.is_blocked,
        blocked_bot=u.blocked_bot,
        created_at=u.created_at,
    )


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


@router.post("/promote", response_model=OkOut)
async def promote_reseller(
    body: PromoteResellerIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    """Promote an existing (bot) user to reseller — super-admin only, audited."""
    ident = body.identifier.strip().lstrip("@")
    u = (
        await User.filter(id=int(ident)).first()
        if ident.isdigit()
        else await User.filter(username__iexact=ident).first()
    )
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if u.role >= User.Role.reseller:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Already a reseller or higher"
        )
    u.role = User.Role.reseller
    await u.save(update_fields=["role"])
    await record_audit(
        action="user.update",
        actor=actor,
        target_type="user",
        target_id=u.id,
        target_label=u.username or u.name,
        detail={"promoted_to": "reseller"},
    )
    return OkOut(ok=True, status=str(u.id))


@router.get("/{reseller_id}/children", response_model=UsersPage)
async def reseller_children(
    reseller_id: int,
    _: User = Depends(require_role(User.Role.admin)),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> UsersPage:
    q = User.filter(parent_id=reseller_id)
    total = await q.count()
    rows = await q.order_by("-created_at").offset((page - 1) * per_page).limit(per_page)
    return UsersPage(items=[_user_item(u) for u in rows], total=total)


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
