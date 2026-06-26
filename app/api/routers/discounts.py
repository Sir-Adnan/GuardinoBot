"""Discount codes. Admin+ only. Full CRUD + an activate toggle."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.exceptions import IntegrityError

from app.api.deps import require_role
from app.api.schemas import (
    DiscountCreateIn,
    DiscountListItem,
    DiscountsPage,
    DiscountUpdateIn,
    OkOut,
    SetEnabledIn,
)
from app.models.service import Discount
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/discounts", tags=["discounts"])


def _validate_pct(p) -> None:
    if p is not None and not (0 <= int(p) <= 100):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "percentage must be 0..100")


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


@router.post("", response_model=DiscountListItem, status_code=status.HTTP_201_CREATED)
async def create_discount(
    body: DiscountCreateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> DiscountListItem:
    _validate_pct(body.percentage)
    code = (body.code or "").strip() or Discount.generate_code()
    data = body.model_dump()
    data["code"] = code
    try:
        d = await Discount.create(**data)
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "A discount with this code exists")
    await record_audit(
        action="discount.create",
        actor=actor,
        target_type="discount",
        target_id=d.id,
        target_label=d.code,
        detail={"percentage": d.percentage},
    )
    return _item(d)


@router.patch("/{discount_id}", response_model=DiscountListItem)
async def update_discount(
    discount_id: int,
    body: DiscountUpdateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> DiscountListItem:
    d = await Discount.filter(id=discount_id).first()
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount not found")
    dump = body.model_dump(exclude_unset=True)
    if "percentage" in dump:
        _validate_pct(dump["percentage"])
    if "code" in dump:
        dump["code"] = (dump["code"] or "").strip() or None
    for k, v in dump.items():
        setattr(d, k, v)
    try:
        await d.save()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "A discount with this code exists")
    await record_audit(
        action="discount.update",
        actor=actor,
        target_type="discount",
        target_id=d.id,
        target_label=d.code,
        detail={"changed": list(dump)},
    )
    return _item(d)


@router.delete("/{discount_id}")
async def delete_discount(
    discount_id: int,
    actor: User = Depends(require_role(User.Role.admin)),
) -> dict:
    d = await Discount.filter(id=discount_id).first()
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount not found")
    did, code = d.id, d.code
    await d.delete()  # clears M2M links (services / used_by); no RESTRICT FKs
    await record_audit(
        action="discount.delete",
        actor=actor,
        target_type="discount",
        target_id=did,
        target_label=code,
    )
    return {"ok": True}


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
