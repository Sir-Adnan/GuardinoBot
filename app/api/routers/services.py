"""Services (sales plans). Admin+ management: list, detail, edit, reorder,
duplicate, delete. Provisioning fields (inbounds / panel_config / server) are
read-only here — create-from-scratch with a panel-aware picker is P5b; for now
"duplicate" clones an existing plan's provisioning and the admin edits the rest."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import (
    ServiceButtonUpdateIn,
    ServiceDetail,
    ServiceListItem,
    ServiceReorderIn,
    ServicesPage,
    ServiceUpdateIn,
)
from app.models.proxy import Proxy, Reserve
from app.models.service import Service
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/services", tags=["services"])

_VALID_STYLES = ("primary", "success", "danger")
_RESET_STRATEGIES = {s.value for s in Service.UsageResetStrategy}
_FLOW_VISION = Service.ServiceProxyFlow.xtls_rprx_vision.value


async def _detail(s: Service) -> ServiceDetail:
    proxies_count = await Proxy.filter(service_id=s.id).count()
    reserves_count = await Reserve.filter(service_id=s.id).count()
    base = _item(s).model_dump()
    return ServiceDetail(
        **base,
        all_inbounds=s.all_inbounds,
        inbounds=s.inbounds,
        panel_config=s.panel_config,
        flow=getattr(s.flow, "value", s.flow),
        one_time_only=s.one_time_only,
        users_only=s.users_only,
        create_on_hold_users=s.create_on_hold_users,
        usage_reset_strategy=getattr(
            s.usage_reset_strategy, "value", s.usage_reset_strategy
        ),
        append_available_data_renew=s.append_available_data_renew,
        priority=s.priority,
        proxies_count=proxies_count,
        reserves_count=reserves_count,
    )


def _item(s: Service) -> ServiceListItem:
    server = s.server if s.server_id else None
    return ServiceListItem(
        id=s.id,
        name=s.name,
        data_limit=s.data_limit,
        expire_duration=s.expire_duration,
        price=s.price,
        purchaseable=s.purchaseable,
        renewable=s.renewable,
        is_test_service=s.is_test_service,
        resellers_only=s.resellers_only,
        server_id=s.server_id,
        server_name=(server.name or server.host) if server else None,
        panel_type=str(getattr(server.panel_type, "value", server.panel_type))
        if server
        else None,
        button_icon=s.button_icon,
        button_style=s.button_style,
    )


@router.get("", response_model=ServicesPage)
async def list_services(
    _: User = Depends(require_role(User.Role.admin)),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> ServicesPage:
    q = Service.all().prefetch_related("server").order_by("priority", "id")
    total = await q.count()
    rows = await q.offset((page - 1) * per_page).limit(per_page)
    return ServicesPage(items=[_item(s) for s in rows], total=total)


@router.get("/{service_id}", response_model=ServiceDetail)
async def get_service(
    service_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ServiceDetail:
    s = await Service.filter(id=service_id).prefetch_related("server").first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return await _detail(s)


@router.patch("/{service_id}", response_model=ServiceDetail)
async def update_service(
    service_id: int,
    body: ServiceUpdateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> ServiceDetail:
    s = await Service.filter(id=service_id).prefetch_related("server").first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")

    dump = body.model_dump(exclude_unset=True)

    # --- fields needing validation/normalisation ---
    if "usage_reset_strategy" in dump:
        v = dump.pop("usage_reset_strategy")
        if v not in _RESET_STRATEGIES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid usage_reset_strategy")
        s.usage_reset_strategy = Service.UsageResetStrategy(v)
    if "flow" in dump:
        v = (dump.pop("flow") or "").strip()
        if v in ("", "none", "None"):
            s.flow = Service.ServiceProxyFlow.none
        elif v == _FLOW_VISION:
            s.flow = Service.ServiceProxyFlow.xtls_rprx_vision
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid flow")
    if "button_icon" in dump:
        s.button_icon = (dump.pop("button_icon") or "").strip() or None
    if "button_style" in dump:
        bs = (dump.pop("button_style") or "").strip()
        s.button_style = bs if bs in _VALID_STYLES else None
    for fld in ("data_limit", "expire_duration", "price"):
        if fld in dump and dump[fld] is not None and dump[fld] < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{fld} must be ≥ 0")

    for k, v in dump.items():
        setattr(s, k, v)
    await s.save()
    await record_audit(
        action="service.update",
        actor=actor,
        target_type="service",
        target_id=str(s.id),
        target_label=s.name,
        detail={"changed": list(body.model_dump(exclude_unset=True))},
    )
    return await _detail(s)


@router.post("/{service_id}/duplicate", response_model=ServiceDetail)
async def duplicate_service(
    service_id: int,
    actor: User = Depends(require_role(User.Role.admin)),
) -> ServiceDetail:
    """Clone a plan (incl. its panel provisioning) as a non-purchaseable draft to
    edit. M2M links (discounts/menus/filters) are NOT copied — re-attach as needed."""
    src = await Service.filter(id=service_id).first()
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    clone = Service(
        name=f"{src.name} (copy)"[:64],
        data_limit=src.data_limit,
        expire_duration=src.expire_duration,
        all_inbounds=src.all_inbounds,
        inbounds=src.inbounds,
        flow=src.flow,
        panel_config=src.panel_config,
        price=src.price,
        one_time_only=src.one_time_only,
        is_test_service=src.is_test_service,
        priority=src.priority,
        purchaseable=False,  # draft until the admin reviews + enables
        renewable=src.renewable,
        resellers_only=src.resellers_only,
        users_only=src.users_only,
        user_filter=src.user_filter,
        create_on_hold_users=src.create_on_hold_users,
        usage_reset_strategy=src.usage_reset_strategy,
        append_available_data_renew=src.append_available_data_renew,
        server_id=src.server_id,
        button_icon=src.button_icon,
        button_style=src.button_style,
    )
    await clone.save()
    await clone.fetch_related("server")
    await record_audit(
        action="service.create",
        actor=actor,
        target_type="service",
        target_id=str(clone.id),
        target_label=clone.name,
        detail={"duplicated_from": src.id},
    )
    return await _detail(clone)


@router.post("/reorder")
async def reorder_services(
    body: ServiceReorderIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> dict:
    """Set display order: priority = position in the given full id list."""
    for idx, sid in enumerate(body.ids):
        await Service.filter(id=sid).update(priority=idx)
    await record_audit(
        action="service.reorder",
        actor=actor,
        target_type="service",
        detail={"count": len(body.ids)},
    )
    return {"ok": True}


@router.delete("/{service_id}")
async def delete_service(
    service_id: int,
    actor: User = Depends(require_role(User.Role.admin)),
) -> dict:
    s = await Service.filter(id=service_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    # Guard: reserves RESTRICT the delete at the DB level; proxies would be orphaned
    # (SET_NULL) and lose their plan link. Block and let the admin resolve first.
    proxies_count = await Proxy.filter(service_id=s.id).count()
    reserves_count = await Reserve.filter(service_id=s.id).count()
    if proxies_count or reserves_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"In use by {proxies_count} subscription(s) and {reserves_count} reserve(s); "
            "resolve them before deleting.",
        )
    sid, name = s.id, s.name
    await s.delete()
    await record_audit(
        action="service.delete",
        actor=actor,
        target_type="service",
        target_id=str(sid),
        target_label=name,
    )
    return {"ok": True}


@router.patch("/{service_id}/button", response_model=ServiceListItem)
async def update_service_button(
    service_id: int,
    body: ServiceButtonUpdateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> ServiceListItem:
    """Set the premium emoji / colour shown on this service's button (reply +
    inline). The bot reads the Service row live, so no reload flag is needed."""
    s = await Service.filter(id=service_id).prefetch_related("server").first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")

    changed: dict = {}
    if body.button_icon is not None:
        s.button_icon = body.button_icon.strip() or None
        changed["button_icon"] = s.button_icon
    if body.button_style is not None:
        v = (body.button_style or "").strip()
        s.button_style = v if v in _VALID_STYLES else None
        changed["button_style"] = s.button_style

    if changed:
        await s.save()
        await record_audit(
            action="service.button",
            actor=actor,
            target_type="service",
            target_id=str(s.id),
            target_label=s.name,
            detail=changed,
        )
    return _item(s)
