"""Connected panels (servers). Admin+ only. Add / edit / delete + health.
Passwords + tokens are NEVER returned. Adding/reconnecting validates the
connection through the §6 panel helpers before persisting."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_role
from app.api.schemas import (
    OkOut,
    ServerCreateIn,
    ServerDetail,
    ServerHealth,
    ServerListItem,
    ServersPage,
    ServerUpdateIn,
    SetEnabledIn,
)
from app.models.server import LinkPolicy, PanelType, Server
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/servers", tags=["servers"])

_PANEL_TYPES = {p.value for p in PanelType}
_LINK_POLICIES = {p.value for p in LinkPolicy}


def _enum(v) -> str:
    return str(getattr(v, "value", v) or "")


def _build_url(host: str, port, https: bool) -> str:
    u = (host or "").rstrip("/")
    if port:
        u = f"{u}:{port}"
    return f"{'https' if https else 'http'}://{u}"


async def _connect(panel_type: str, url: str, username: str, password: str):
    """Validate a panel connection and return (token, AdminInfo). Raises a clean
    HTTPException on failure. Mirrors the bot's add-server flow via §6 helpers."""
    from app.panels.base import PanelAuthError, PanelError

    try:
        if panel_type == "marzban":
            from app.panels import marzban

            token = await marzban.fetch_token(url, username, password)
            admin = await marzban.validate_token(url, token)
        elif panel_type == "pasarguard":
            from app.panels import pasarguard

            token = await pasarguard.fetch_token(url, username, password)
            admin = await pasarguard.validate_token(url, token)
        elif panel_type == "guardino":
            from app.panels import guardino

            data = await guardino.login(url, username, password)
            if data.get("requires_2fa"):
                raise PanelAuthError(
                    "2FA is enabled — disable it on the bot account (or use an API token)."
                )
            token = data.get("access_token")
            if not token:
                raise PanelAuthError("Guardino returned no access_token.")
            admin = await guardino.validate(url, token)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown panel_type")
    except (PanelAuthError, PanelError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Connection failed: {str(exc)[:200]}",
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - network/parse errors → 502
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Panel unreachable: {str(exc)[:200]}"
        )
    return token, admin


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


async def _detail(s: Server) -> ServerDetail:
    from app.models.proxy import Proxy
    from app.models.service import Service

    return ServerDetail(
        **_item(s).model_dump(),
        port=s.port,
        https=s.https,
        username=s.username,
        services_count=await Service.filter(server_id=s.id).count(),
        proxies_count=await Proxy.filter(server_id=s.id).count(),
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


@router.get("/{server_id}", response_model=ServerDetail)
async def get_server(
    server_id: int, _: User = Depends(require_role(User.Role.admin))
) -> ServerDetail:
    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return await _detail(s)


@router.post("", response_model=ServerDetail, status_code=status.HTTP_201_CREATED)
async def add_server(
    body: ServerCreateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> ServerDetail:
    """Connect + persist a new panel. Validates credentials before saving;
    password is stored encrypted (PasswordField) and never returned."""
    if body.panel_type not in _PANEL_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid panel_type")
    link_policy = body.link_policy or LinkPolicy.master_first.value
    if link_policy not in _LINK_POLICIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid link_policy")

    url = _build_url(body.host, body.port, body.https)
    token, _admin = await _connect(body.panel_type, url, body.username, body.password)

    s = await Server.create(
        host=body.host,
        port=body.port,
        https=body.https,
        token=token,
        panel_type=PanelType(body.panel_type),
        link_policy=LinkPolicy(link_policy),
        name=body.name or None,
        username=body.username,
        password=body.password,
        is_enabled=True,
    )
    await record_audit(
        action="server.add",
        actor=actor,
        target_type="server",
        target_id=s.id,
        target_label=s.name or s.host,
        detail={"panel_type": body.panel_type},
    )
    return await _detail(s)


@router.patch("/{server_id}", response_model=ServerDetail)
async def update_server(
    server_id: int,
    body: ServerUpdateIn,
    actor: User = Depends(require_role(User.Role.admin)),
) -> ServerDetail:
    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")

    dump = body.model_dump(exclude_unset=True)
    if "link_policy" in dump and dump["link_policy"] not in _LINK_POLICIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid link_policy")

    # If any connection-affecting field changed, re-validate + refresh the token.
    conn_fields = {"host", "port", "https", "username", "password"}
    if conn_fields & dump.keys():
        host = dump.get("host", s.host)
        port = dump.get("port", s.port)
        https = dump.get("https", s.https)
        username = dump.get("username", s.username)
        password = dump.get("password", s.password)
        token, _admin = await _connect(
            _enum(s.panel_type), _build_url(host, port, https), username, password
        )
        s.token = token

    if "link_policy" in dump:
        s.link_policy = LinkPolicy(dump.pop("link_policy"))
    for k, v in dump.items():
        setattr(s, k, v)
    await s.save()
    await record_audit(
        action="server.update",
        actor=actor,
        target_type="server",
        target_id=s.id,
        target_label=s.name or s.host,
        detail={"changed": list(dump) + (["token"] if conn_fields & dump.keys() else [])},
    )
    return await _detail(s)


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    actor: User = Depends(require_role(User.Role.admin)),
) -> dict:
    """Delete a panel. BLOCKED while services/proxies exist — the FK is CASCADE,
    so deleting would wipe live subscriptions. Admin must remove them first."""
    from app.models.proxy import Proxy
    from app.models.service import Service

    s = await Server.filter(id=server_id).first()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    services_count = await Service.filter(server_id=s.id).count()
    proxies_count = await Proxy.filter(server_id=s.id).count()
    if services_count or proxies_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"In use by {services_count} service(s) and {proxies_count} subscription(s); "
            "remove them before deleting (deletion cascades and would wipe them).",
        )
    sid, name = s.id, s.name or s.host
    await s.delete()
    await record_audit(
        action="server.delete",
        actor=actor,
        target_type="server",
        target_id=sid,
        target_label=name,
    )
    return {"ok": True}


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
