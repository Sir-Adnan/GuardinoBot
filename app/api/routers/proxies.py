"""Proxies (user subscriptions). Reseller-scoped to their own subtree."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import ProxiesPage, ProxyListItem
from app.models.proxy import Proxy
from app.models.user import User

router = APIRouter(prefix="/proxies", tags=["proxies"])


def _scope(viewer: User):
    q = Proxy.all()
    if viewer.role < User.Role.admin:
        q = q.filter(user__parent_id=viewer.id)
    return q


def _item(p: Proxy) -> ProxyListItem:
    server = p.server if p.server_id else None
    service = p.service if p.service_id else None
    return ProxyListItem(
        id=p.id,
        username=p.username,
        custom_name=p.custom_name,
        status=str(getattr(p.status, "value", p.status)),
        cost=p.cost,
        user_id=p.user_id,
        server_id=p.server_id,
        server_name=(server.name or server.host) if server else None,
        service_id=p.service_id,
        service_name=service.name if service else None,
        created_at=p.created_at,
    )


@router.get("", response_model=ProxiesPage)
async def list_proxies(
    viewer: User = Depends(require_role(User.Role.reseller)),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    server_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
) -> ProxiesPage:
    q = _scope(viewer).prefetch_related("server", "service")
    if search:
        q = q.filter(username__icontains=search.strip())
    if server_id:
        q = q.filter(server_id=server_id)
    if user_id:
        q = q.filter(user_id=user_id)
    if status_filter:
        q = q.filter(status=status_filter)
    total = await q.count()
    rows = await q.order_by("-created_at").offset((page - 1) * per_page).limit(per_page)
    return ProxiesPage(items=[_item(p) for p in rows], total=total)


@router.get("/{proxy_id}", response_model=ProxyListItem)
async def get_proxy(
    proxy_id: int, viewer: User = Depends(require_role(User.Role.reseller))
) -> ProxyListItem:
    p = (
        await _scope(viewer)
        .filter(id=proxy_id)
        .prefetch_related("server", "service")
        .first()
    )
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proxy not found")
    return _item(p)
