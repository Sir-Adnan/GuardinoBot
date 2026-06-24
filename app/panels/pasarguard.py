"""PasarGuard panel adapter (API v5).

PasarGuard is the spiritual successor to Marzban and shares most of its REST
surface (``/api/admin/token`` OAuth2 password flow, ``/api/user`` CRUD, same
``UserStatus`` and ``data_limit_reset_strategy`` values). The two meaningful
differences, handled here:

  * provisioning uses **group_ids** (from ``/api/groups``) instead of Marzban's
    ``inbounds`` dict, and **proxy_settings** instead of ``proxies``;
  * ``expire`` may come back as an ISO datetime string (Marzban always used an
    int epoch) — normalized to epoch seconds.

Uses a small in-module ``httpx`` client (no generated package) per the agreed
design. Auth: the server's stored bearer ``token`` is tried first; on 401 we
re-authenticate from the stored username/password (if present) and retry once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.logger import get_logger
from app.panels.base import (
    AdminInfo,
    BasePanel,
    ModifyUserParams,
    PanelAuthError,
    PanelError,
    PanelType,
    PanelUser,
    PanelUserStatus,
)

logger = get_logger("panels/pasarguard")

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


def _to_epoch(value: Any) -> Optional[int]:
    """Normalize PasarGuard ``expire`` (int epoch | ISO str | 0 | null) to an
    int epoch, or None for unlimited / unset."""
    if value in (None, 0, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            return None
    return None


def _status(value: Any) -> PanelUserStatus:
    try:
        return PanelUserStatus(str(value))
    except ValueError:
        return PanelUserStatus.active


class PasarGuardPanel(BasePanel):
    panel_type = PanelType.pasarguard
    uses_groups = True

    def __init__(self, server) -> None:
        super().__init__(server)
        self._token: Optional[str] = server.token or None
        self._client: Optional[httpx.AsyncClient] = None

    # -- transport -------------------------------------------------------------
    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.server.url, timeout=_TIMEOUT)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _authenticate(self) -> str:
        """Fetch a fresh bearer token from username/password."""
        if not (self.server.username and self.server.password):
            raise PanelAuthError(
                "PasarGuard server has no stored credentials to (re)authenticate",
                server_id=self.server_id,
            )
        try:
            resp = await self._http().post(
                "/api/admin/token",
                data={
                    "grant_type": "password",
                    "username": self.server.username,
                    "password": self.server.password,
                },
            )
        except httpx.HTTPError as exc:
            raise PanelError(str(exc), server_id=self.server_id) from exc
        if resp.status_code != 200:
            raise PanelAuthError(
                "PasarGuard token request failed",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        token = resp.json().get("access_token")
        if not token:
            raise PanelAuthError("PasarGuard returned no access_token", server_id=self.server_id)
        self._token = token
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        params: Any = None,
        _retried: bool = False,
    ) -> httpx.Response:
        """Authenticated request with single 401 -> re-auth -> retry."""
        if not self._token:
            await self._authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = await self._http().request(
                method, path, json=json, data=data, params=params, headers=headers
            )
        except httpx.HTTPError as exc:
            raise PanelError(str(exc), server_id=self.server_id) from exc
        if resp.status_code == 401 and not _retried and self.server.username:
            await self._authenticate()
            return await self._request(
                method, path, json=json, data=data, params=params, _retried=True
            )
        return resp

    @staticmethod
    def _ok(resp: httpx.Response, *, allow: tuple[int, ...] = (200, 201, 204)) -> None:
        if resp.status_code in allow:
            return
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:  # noqa: BLE001 - response may not be JSON
            detail = resp.text[:200]
        raise PanelError(
            f"PasarGuard {resp.request.method} {resp.request.url.path} -> "
            f"{resp.status_code}: {detail}",
            status_code=resp.status_code,
        )

    # -- parsing ---------------------------------------------------------------
    def _to_user(self, data: dict) -> PanelUser:
        return PanelUser(
            username=data.get("username", ""),
            status=_status(data.get("status")),
            used_traffic=int(data.get("used_traffic") or 0),
            lifetime_used_traffic=int(data.get("lifetime_used_traffic") or 0),
            data_limit=data.get("data_limit") or None,
            expire=_to_epoch(data.get("expire")),
            data_limit_reset_strategy=str(data.get("data_limit_reset_strategy") or "no_reset"),
            subscription_url=data.get("subscription_url") or "",
            # PasarGuard UserResponse has no inline `links`; configs come from
            # the subscription endpoint. Left empty; callers fall back to
            # subscription_url for display.
            links=list(data.get("links") or []),
            proxies=dict(data.get("proxy_settings") or {}),
            group_ids=list(data.get("group_ids") or []),
            remote_id=data.get("id"),
            raw=data,
        )

    def _provisioning(self, service: Any) -> dict:
        """Build PasarGuard provisioning from Service.panel_config.

        Expected panel_config shape for PasarGuard:
            {"group_ids": [1, 2], "proxy_settings": {...optional...}}
        proxy_settings is optional: when omitted PasarGuard auto-generates all
        protocols. Read defensively so it is safe before the panel_config
        migration lands.
        """
        config = getattr(service, "panel_config", None) or {}
        out: dict = {}
        group_ids = config.get("group_ids")
        if group_ids:
            out["group_ids"] = [int(g) for g in group_ids]
        proxy_settings = config.get("proxy_settings")
        if proxy_settings:
            out["proxy_settings"] = proxy_settings
        return out

    # -- BasePanel impl --------------------------------------------------------
    async def get_admin(self) -> AdminInfo:
        resp = await self._request("GET", "/api/admin")
        self._ok(resp, allow=(200,))
        data = resp.json()
        role = data.get("role") or {}
        return AdminInfo(
            username=data.get("username", ""),
            is_sudo=bool(role.get("is_owner", False)),
            raw=data,
        )

    async def _allowed_group_ids(self) -> Optional[list[int]]:
        """The group ids the current admin may assign, or ``None`` when
        unrestricted (owner, or no group scope set).

        PasarGuard is role-based: only owners can list every group via
        ``/api/groups``; a restricted admin is 403'd there and instead carries
        its assignable groups in ``role.access.allowed_group_ids`` on its own
        admin record (``/api/admin``)."""
        resp = await self._request("GET", "/api/admin")
        if resp.status_code != 200:
            return None
        role = resp.json().get("role") or {}
        if role.get("is_owner"):
            return None
        ids = (role.get("access") or {}).get("allowed_group_ids")
        if ids is None:
            return None  # unrestricted
        return [int(i) for i in ids]

    async def _list_groups(self, *, detailed: bool) -> Optional[list[dict]]:
        """List groups, normalized to ``{id, name, inbound_tags}``.

        Returns ``None`` when the admin is forbidden (403) so the caller can
        fall back. ``detailed`` hits ``/api/groups`` (with ``inbound_tags``);
        otherwise ``/api/groups/simple`` (id + name only, lighter perms)."""
        path = "/api/groups" if detailed else "/api/groups/simple"
        resp = await self._request("GET", path, params={"limit": 1000})
        if resp.status_code == 403:
            return None
        self._ok(resp, allow=(200,))
        out: list[dict] = []
        for g in resp.json().get("groups", []):
            out.append(
                {
                    "id": g.get("id"),
                    "name": g.get("name") or str(g.get("id")),
                    "inbound_tags": list(g.get("inbound_tags", []) or []) if detailed else [],
                }
            )
        return out

    async def get_inbounds(self) -> dict:
        """Return the groups this admin may assign — PasarGuard's analogue of
        Marzban's inbounds — handling restricted (non-owner) admins.

        Owners get the full ``/api/groups`` list; restricted admins fall back to
        ``/api/groups/simple`` and finally to the id-only ``allowed_group_ids``
        from their admin record, so a non-owner bot account no longer dead-ends
        on a 403 when building a service.
        """
        allowed_ids = await self._allowed_group_ids()

        groups = await self._list_groups(detailed=True)
        if groups is None:
            groups = await self._list_groups(detailed=False)
        if groups is None:
            # No group-listing permission at all: build from the admin's own
            # allowed ids (names unknown → shown by id).
            groups = [
                {"id": gid, "name": str(gid), "inbound_tags": []}
                for gid in (allowed_ids or [])
            ]
        elif allowed_ids is not None:
            wanted = set(allowed_ids)
            groups = [g for g in groups if g.get("id") in wanted]

        flat: dict[str, list[str]] = {}
        for g in groups:
            for tag in g.get("inbound_tags", []) or []:
                flat.setdefault("inbounds", []).append(tag)
        return {"groups": groups, "inbounds": flat.get("inbounds", [])}

    async def create_user(
        self,
        *,
        username: str,
        service: Any,
        data_limit: Optional[int],
        expire: Optional[int],
        status: Optional[PanelUserStatus] = None,
        data_limit_reset_strategy: Optional[str] = None,
        on_hold_expire_duration: Optional[int] = None,
        on_hold_timeout: Optional[int] = None,
    ) -> PanelUser:
        body: dict[str, Any] = {
            "username": username,
            "data_limit": int(data_limit or 0),
            "data_limit_reset_strategy": data_limit_reset_strategy or "no_reset",
        }
        if expire is not None:
            body["expire"] = int(expire)
        if status is not None:
            body["status"] = PanelUserStatus(status).value
        if on_hold_expire_duration is not None:
            body["on_hold_expire_duration"] = int(on_hold_expire_duration)
        if on_hold_timeout is not None:
            # JSON body: normalize datetime -> epoch int (PasarGuard accepts int).
            body["on_hold_timeout"] = (
                int(on_hold_timeout.timestamp())
                if hasattr(on_hold_timeout, "timestamp")
                else int(on_hold_timeout)
            )
        body.update(self._provisioning(service))

        resp = await self._request("POST", "/api/user", json=body)
        self._ok(resp, allow=(200, 201))
        return self._to_user(resp.json())

    async def modify_user(self, username: str, params: ModifyUserParams) -> PanelUser:
        body: dict[str, Any] = {}
        if params.is_set("status"):
            body["status"] = PanelUserStatus(params.status).value
        if params.is_set("expire"):
            body["expire"] = params.expire
        if params.is_set("data_limit"):
            body["data_limit"] = params.data_limit
        if params.is_set("data_limit_reset_strategy"):
            body["data_limit_reset_strategy"] = params.data_limit_reset_strategy
        if params.is_set("group_ids"):
            body["group_ids"] = params.group_ids
        if params.is_set("proxies"):
            body["proxy_settings"] = params.proxies
        if params.is_set("note"):
            body["note"] = params.note

        resp = await self._request("PUT", f"/api/user/{username}", json=body)
        self._ok(resp, allow=(200,))
        return self._to_user(resp.json())

    async def get_user(self, username: str) -> Optional[PanelUser]:
        resp = await self._request("GET", f"/api/user/{username}")
        if resp.status_code == 404:
            return None
        self._ok(resp, allow=(200,))
        return self._to_user(resp.json())

    async def get_users(self, usernames: list[str]) -> list[PanelUser]:
        if not usernames:
            return []
        resp = await self._request(
            "GET", "/api/users", params=[("username", u) for u in usernames]
        )
        self._ok(resp, allow=(200,))
        return [self._to_user(u) for u in resp.json().get("users", [])]

    async def remove_user(self, username: str) -> bool:
        resp = await self._request("DELETE", f"/api/user/{username}")
        if resp.status_code in (204, 200, 404):
            return True
        self._ok(resp)
        return True

    async def reset_usage(self, username: str) -> PanelUser:
        resp = await self._request("POST", f"/api/user/{username}/reset")
        self._ok(resp, allow=(200,))
        return self._to_user(resp.json())

    async def service_modify_params(
        self, service: Any, existing: Optional[PanelUser] = None
    ) -> ModifyUserParams:
        # Re-apply the service's groups; leave proxy_settings untouched so the
        # user's existing credentials/configs survive the change.
        config = getattr(service, "panel_config", None) or {}
        params = ModifyUserParams()
        group_ids = config.get("group_ids")
        if group_ids:
            params.group_ids = [int(g) for g in group_ids]
        return params

    async def reset_proxy_credentials(self, username: str, service: Any) -> PanelUser:
        # PasarGuard has no "rotate proxy creds, keep sub" primitive yet.
        raise PanelError(
            "Reset password is not supported on PasarGuard yet",
            server_id=self.server_id,
        )

    async def revoke_subscription(self, username: str) -> PanelUser:
        resp = await self._request("POST", f"/api/user/{username}/revoke_sub")
        self._ok(resp, allow=(200,))
        return self._to_user(resp.json())


async def fetch_token(url: str, username: str, password: str) -> str:
    """One-shot token exchange used by the server-setup flow (admin adds a
    PasarGuard server with username/password). Mirrors Marzban's flow."""
    async with httpx.AsyncClient(base_url=url, timeout=_TIMEOUT) as client:
        resp = await client.post(
            "/api/admin/token",
            data={"grant_type": "password", "username": username, "password": password},
        )
    if resp.status_code != 200:
        raise PanelAuthError("PasarGuard token request failed", status_code=resp.status_code)
    token = resp.json().get("access_token")
    if not token:
        raise PanelAuthError("PasarGuard returned no access_token")
    return token


async def validate_token(url: str, token: str) -> AdminInfo:
    """Validate a PasarGuard bearer token and return admin identity."""
    async with httpx.AsyncClient(base_url=url, timeout=_TIMEOUT) as client:
        resp = await client.get("/api/admin", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise PanelAuthError("PasarGuard admin validation failed", status_code=resp.status_code)
    data = resp.json()
    role = data.get("role") or {}
    return AdminInfo(username=data.get("username", ""), is_sudo=bool(role.get("is_owner", False)), raw=data)
