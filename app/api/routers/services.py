"""Services (sales plans). Admin+ management view."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import ServiceButtonUpdateIn, ServiceListItem, ServicesPage
from app.models.service import Service
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/services", tags=["services"])

_VALID_STYLES = ("primary", "success", "danger")


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


@router.get("/{service_id}", response_model=ServiceListItem)
async def get_service(
    service_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ServiceListItem:
    s = await Service.filter(id=service_id).prefetch_related("server").first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return _item(s)


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
