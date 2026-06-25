"""Users resource. Resellers are scoped to their own subtree; admins+ see all."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.expressions import Q

from app.api.deps import require_role
from app.api.schemas import (
    ROLE_NAMES,
    OkOut,
    SetBlockedIn,
    UserDetail,
    UserListItem,
    UsersPage,
)
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


def _item(u: User) -> UserListItem:
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


def _scope(viewer: User):
    """Resellers see only their own children; admins/super_users see everyone."""
    q = User.all()
    if viewer.role < User.Role.admin:
        q = q.filter(parent_id=viewer.id)
    return q


@router.get("", response_model=UsersPage)
async def list_users(
    viewer: User = Depends(require_role(User.Role.reseller)),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
) -> UsersPage:
    q = _scope(viewer)
    if search:
        s = search.strip().lstrip("@")
        cond = Q(username__icontains=s) | Q(name__icontains=s)
        if s.isdigit():
            cond = cond | Q(id=int(s))
        q = q.filter(cond)
    total = await q.count()
    rows = await q.order_by("-created_at").offset((page - 1) * per_page).limit(per_page)
    return UsersPage(items=[_item(u) for u in rows], total=total)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: int,
    viewer: User = Depends(require_role(User.Role.reseller)),
) -> UserDetail:
    u = await _scope(viewer).filter(id=user_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    balance = await u.get_balance()
    proxies_count = await u.proxies.all().count()
    return UserDetail(
        id=u.id,
        username=u.username,
        name=u.name,
        role=int(u.role),
        role_name=ROLE_NAMES.get(int(u.role), str(int(u.role))),
        is_blocked=u.is_blocked,
        blocked_bot=u.blocked_bot,
        created_at=u.created_at,
        balance=balance,
        is_verified=u.is_verified,
        is_postpaid=u.is_postpaid,
        proxies_count=proxies_count,
    )


@router.post("/{user_id}/block", response_model=OkOut)
async def set_user_blocked(
    user_id: int,
    body: SetBlockedIn,
    _: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    u = await User.filter(id=user_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    u.is_blocked = body.blocked
    await u.save(update_fields=["is_blocked"])
    return OkOut(ok=True)
