"""Service menus — nested sale categories (``ServiceMenu``). Super-admin only.

Lets the owner group plans into (optionally nested) categories shown in the
bot's purchase flow, exactly like the bot's own menu builder. The bot reads
menus live from the DB, so changes here apply without a reload.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from tortoise.exceptions import IntegrityError

from app.api.deps import require_role
from app.api.schemas import (
    MenuCreateIn,
    MenuDetail,
    MenuListItem,
    MenusOut,
    MenuUpdateIn,
)
from app.models.service import Service, ServiceMenu
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/menus", tags=["menus"])

_VALID_STYLES = ("primary", "success", "danger")


def _normalize_button(d: dict) -> None:
    """In place: blank icon → None; style → a valid Bot API style or None."""
    if "button_icon" in d:
        d["button_icon"] = (d["button_icon"] or "").strip() or None
    if "button_style" in d:
        v = (d["button_style"] or "").strip()
        d["button_style"] = v if v in _VALID_STYLES else None


def _item(m: ServiceMenu, services_count: int, children_count: int) -> MenuListItem:
    return MenuListItem(
        id=m.id,
        title=m.title,
        parent_id=m.parent_id,
        purchase=m.purchase,
        renew=m.renew,
        resellers_only=m.resellers_only,
        users_only=m.users_only,
        services_count=services_count,
        children_count=children_count,
        button_icon=m.button_icon,
        button_style=m.button_style,
    )


async def _counts(m: ServiceMenu) -> tuple[int, int]:
    sc = await m.services.all().count()
    cc = await ServiceMenu.filter(parent_id=m.id).count()
    return sc, cc


async def _would_cycle(menu_id: int, new_parent_id: Optional[int]) -> bool:
    """True if setting ``menu_id``'s parent to ``new_parent_id`` would create a
    loop (new parent is the menu itself or one of its descendants)."""
    pid = new_parent_id
    seen = set()
    while pid is not None:
        if pid == menu_id or pid in seen:
            return True
        seen.add(pid)
        parent = await ServiceMenu.filter(id=pid).values("parent_id")
        pid = parent[0]["parent_id"] if parent else None
    return False


@router.get("", response_model=MenusOut)
async def list_menus(
    _: User = Depends(require_role(User.Role.super_user)),
) -> MenusOut:
    menus = await ServiceMenu.all().order_by("id")
    items = []
    for m in menus:
        sc, cc = await _counts(m)
        items.append(_item(m, sc, cc))
    return MenusOut(items=items)


@router.get("/{menu_id}", response_model=MenuDetail)
async def get_menu(
    menu_id: int, _: User = Depends(require_role(User.Role.super_user))
) -> MenuDetail:
    m = await ServiceMenu.filter(id=menu_id).prefetch_related("services").first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    service_ids = [s.id for s in m.services]
    cc = await ServiceMenu.filter(parent_id=menu_id).count()
    return MenuDetail(
        **_item(m, len(service_ids), cc).model_dump(),
        description=m.description,
        service_ids=service_ids,
    )


async def _set_services(m: ServiceMenu, service_ids: list[int]) -> None:
    await m.services.clear()
    if service_ids:
        svcs = await Service.filter(id__in=service_ids)
        await m.services.add(*svcs)


@router.post("", response_model=MenuDetail, status_code=status.HTTP_201_CREATED)
async def create_menu(
    body: MenuCreateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> MenuDetail:
    data = body.model_dump()
    service_ids = data.pop("service_ids", []) or []
    _normalize_button(data)
    if data.get("parent_id") and not await ServiceMenu.filter(
        id=data["parent_id"]
    ).exists():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent menu not found")
    try:
        m = await ServiceMenu.create(**data)
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "A menu with this title exists")
    await _set_services(m, service_ids)
    await record_audit(
        action="menu.create",
        actor=actor,
        target_type="menu",
        target_id=m.id,
        target_label=m.title,
        detail={"parent_id": m.parent_id, "services": len(service_ids)},
    )
    return await get_menu(m.id, actor)


@router.patch("/{menu_id}", response_model=MenuDetail)
async def update_menu(
    menu_id: int,
    body: MenuUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> MenuDetail:
    m = await ServiceMenu.filter(id=menu_id).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    dump = body.model_dump(exclude_unset=True)
    service_ids = dump.pop("service_ids", None)
    _normalize_button(dump)
    if "parent_id" in dump and await _would_cycle(menu_id, dump["parent_id"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "A menu cannot be nested under itself"
        )
    for k, v in dump.items():
        setattr(m, k, v)
    try:
        await m.save()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "A menu with this title exists")
    if service_ids is not None:
        await _set_services(m, service_ids)
    await record_audit(
        action="menu.update",
        actor=actor,
        target_type="menu",
        target_id=m.id,
        target_label=m.title,
        detail={"changed": list(dump)},
    )
    return await get_menu(m.id, actor)


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> dict:
    m = await ServiceMenu.filter(id=menu_id).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    mid, title = m.id, m.title
    await m.delete()  # cascades child menus (FK CASCADE) + clears M2M links
    await record_audit(
        action="menu.delete",
        actor=actor,
        target_type="menu",
        target_id=mid,
        target_label=title,
    )
    return {"ok": True}
