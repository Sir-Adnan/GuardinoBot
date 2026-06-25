"""Connected panels (servers). Admin+ only. Credentials are never exposed."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import (
    OkOut,
    ServerHealth,
    ServerListItem,
    ServersPage,
    SetEnabledIn,
)
from app.models.server import Server
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/servers", tags=["servers"])


def _enum(v) -> str:
    return str(getattr(v, "value", v) or "")


def _item(s: Server) -> ServerListItem:
    return ServerListItem(
        id=s.id,
        name=s.name,
        host=s.host,
        panel_type=_enum(s.panel_type),
        link_policy=_enum(s.link_policy) or None,
        is_enabled=s.is_enabled,
        total_proxies=s.total_proxies,
        url=s.url,
    )


@router.get("", response_model=ServersPage)
async def list_servers(
    _: User = Depends(require_role(User.Role.admin)),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> ServersPage:
    q = Server.all().order_by("id")
    total = await q.count()
    rows = await q.offset((page - 1) * per_page).limit(per_page)
    return ServersPage(items=[_item(s) for s in rows], total=total)


@router.get("/{server_id}", response_model=ServerListItem)
async def get_server(
    server_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ServerListItem:
    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return _item(s)


@router.get("/{server_id}/health", response_model=ServerHealth)
async def server_health(
    server_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ServerHealth:
    """Live ping via the §6 adapter (panel-agnostic get_admin). Builds a fresh
    adapter (the bot's cached PanelRegistry isn't loaded in the API process)."""
    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    try:
        from app.panels.registry import build_panel

        panel = build_panel(s)
        try:
            admin = await panel.get_admin()
            return ServerHealth(ok=True, username=admin.username, is_sudo=admin.is_sudo)
        finally:
            await panel.aclose()
    except Exception as exc:  # noqa: BLE001 - report any failure as unhealthy
        return ServerHealth(
            ok=False,
            error=str(exc)[:200],
            status_code=getattr(exc, "status_code", None),
        )


@router.post("/{server_id}/enabled", response_model=OkOut)
async def set_server_enabled(
    server_id: int,
    body: SetEnabledIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> OkOut:
    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    s.is_enabled = body.enabled
    await s.save(update_fields=["is_enabled"])
    await record_audit(
        action="server.enable" if body.enabled else "server.disable",
        actor=actor,
        target_type="server",
        target_id=s.id,
        target_label=s.name or s.host,
        detail={"panel_type": _enum(s.panel_type)},
    )
    return OkOut(ok=True)
