"""Discount codes. Admin+ only. List/detail + an activate toggle."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import DiscountListItem, DiscountsPage, OkOut, SetEnabledIn
from app.models.service import Discount
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/discounts", tags=["discounts"])


def _item(d: Discount) -> DiscountListItem:
    return DiscountListItem(
        id=d.id,
        code=d.code,
        percentage=d.percentage,
        is_active=d.is_active,
        on_purchase=d.on_purchase,
        on_renew=d.on_renew,
        once_per_user=d.once_per_user,
        used_times=d.used_times,
        use_counts=d.use_counts,
        expires_at=d.expires_at,
        created_at=d.created_at,
    )


@router.get("", response_model=DiscountsPage)
async def list_discounts(
    _: User = Depends(require_role(User.Role.admin)),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
) -> DiscountsPage:
    q = Discount.all()
    if search:
        q = q.filter(code__icontains=search.strip())
    total = await q.count()
    rows = await q.order_by("-created_at").offset((page - 1) * per_page).limit(per_page)
    return DiscountsPage(items=[_item(d) for d in rows], total=total)


@router.get("/{discount_id}", response_model=DiscountListItem)
async def get_discount(
    discount_id: int, _: User = Depends(require_role(User.Role.admin))
) -> DiscountListItem:
    d = await Discount.filter(id=discount_id).first()
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount not found")
    return _item(d)


@router.post("/{discount_id}/active", response_model=OkOut)
async def set_discount_active(
    discount_id: int,
    body: SetEnabledIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    d = await Discount.filter(id=discount_id).first()
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount not found")
    d.is_active = body.enabled
    await d.save(update_fields=["is_active"])
    await record_audit(
        action="discount.activate" if body.enabled else "discount.deactivate",
        actor=actor,
        target_type="discount",
        target_id=d.id,
        target_label=d.code,
    )
    return OkOut(ok=True)
