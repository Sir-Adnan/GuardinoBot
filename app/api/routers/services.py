"""Services (sales plans). Admin+ management view."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import ServiceListItem, ServicesPage
from app.models.service import Service
from app.models.user import User

router = APIRouter(prefix="/services", tags=["services"])


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
