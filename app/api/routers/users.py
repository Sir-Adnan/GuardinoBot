"""Users resource. Resellers are scoped to their own subtree; admins+ see all."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.expressions import Q

from app.api.deps import require_role
from app.api.schemas import (
    ROLE_NAMES,
    BalanceAdjustIn,
    OkOut,
    SetBlockedIn,
    UserDetail,
    UserListItem,
    UserUpdateIn,
    UsersPage,
)
from app.models.user import Invoice, Transaction, User, UserSetting
from app.utils.audit import record_audit

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
    role: Optional[int] = Query(None, ge=0, le=4),
    blocked: Optional[str] = Query(None),  # "blocked" | "bot" | "active"
) -> UsersPage:
    q = _scope(viewer)
    if search:
        s = search.strip().lstrip("@")
        cond = Q(username__icontains=s) | Q(name__icontains=s)
        if s.isdigit():
            cond = cond | Q(id=int(s))
        q = q.filter(cond)
    if role is not None:
        q = q.filter(role=role)
    if blocked == "blocked":
        q = q.filter(is_blocked=True)
    elif blocked == "bot":
        q = q.filter(blocked_bot=True)
    elif blocked == "active":
        q = q.filter(is_blocked=False, blocked_bot=False)
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
    st = await UserSetting.get_or_none(user_id=u.id)
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
        max_post_paid_credit=u.max_post_paid_credit,
        daily_test_services=getattr(st, "daily_test_services", 0) or 0,
        discount_percentage=getattr(st, "discount_percentage", 0) or 0,
        proxy_username_prefix=getattr(st, "proxy_username_prefix", None),
        parent_id=u.parent_id,
        referrer_id=u.referrer_id,
    )


@router.post("/{user_id}/block", response_model=OkOut)
async def set_user_blocked(
    user_id: int,
    body: SetBlockedIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    u = await User.filter(id=user_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    u.is_blocked = body.blocked
    await u.save(update_fields=["is_blocked"])
    await record_audit(
        action="user.block" if body.blocked else "user.unblock",
        actor=actor,
        target_type="user",
        target_id=u.id,
        target_label=u.username or u.name,
    )
    return OkOut(ok=True)


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: int,
    body: UserUpdateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> UserDetail:
    """Edit account fields. Role changes require super-admin (privilege-escalation
    guard). Setting fields (test count / discount % / prefix) live on UserSetting."""
    u = await User.filter(id=user_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    dump = body.model_dump(exclude_unset=True)
    changed: list[str] = []

    if "role" in dump and dump["role"] is not None:
        if actor.role < User.Role.super_user:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Only a super-admin can change roles"
            )
        if dump["role"] not in tuple(int(r) for r in User.Role):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
        u.role = User.Role(dump["role"])
        changed.append("role")
    if "is_postpaid" in dump:
        u.is_postpaid = bool(dump["is_postpaid"])
        changed.append("is_postpaid")
    if "max_post_paid_credit" in dump and dump["max_post_paid_credit"] is not None:
        u.max_post_paid_credit = max(0, int(dump["max_post_paid_credit"]))
        changed.append("max_post_paid_credit")
    if changed:
        await u.save()

    # UserSetting fields
    set_fields = {
        k: dump[k]
        for k in ("daily_test_services", "discount_percentage", "proxy_username_prefix")
        if k in dump
    }
    if set_fields:
        st, _ = await UserSetting.get_or_create(user_id=u.id)
        if "daily_test_services" in set_fields:
            st.daily_test_services = max(0, int(set_fields["daily_test_services"] or 0))
        if "discount_percentage" in set_fields:
            st.discount_percentage = max(0, min(100, int(set_fields["discount_percentage"] or 0)))
        if "proxy_username_prefix" in set_fields:
            st.proxy_username_prefix = (set_fields["proxy_username_prefix"] or "").strip()[:25] or None
        await st.save()
        changed += list(set_fields)

    if changed:
        await record_audit(
            action="user.update",
            actor=actor,
            target_type="user",
            target_id=u.id,
            target_label=u.username or u.name,
            detail={"changed": changed},
        )
    return await get_user(u.id, actor)


@router.post("/{user_id}/balance", response_model=OkOut)
async def adjust_balance(
    user_id: int,
    body: BalanceAdjustIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    """Charge (add) or decharge (subtract) a user's balance — super-admin only,
    mirroring the bot's /charge (Transaction) and /decharge (Invoice) so balance
    math + stats stay consistent. Audited."""
    u = await User.filter(id=user_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    amount = int(body.amount)
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Amount must be > 0")

    if body.direction == "charge":
        await Transaction.create(
            type=Transaction.PaymentType.by_admin,
            status=Transaction.Status.finished,
            amount=amount,
            amount_paid=amount,
            user=u,
        )
        signed = amount
    elif body.direction == "decharge":
        await Invoice.create(amount=amount, type=Invoice.Type.by_admin, user=u)
        signed = -amount
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "direction must be charge|decharge")

    await record_audit(
        action="balance.adjust",
        actor=actor,
        target_type="user",
        target_id=u.id,
        target_label=u.username or u.name,
        amount=float(signed),
        detail={"direction": body.direction},
    )
    return OkOut(ok=True)
