"""Guardino Hub panel adapter (API v0.1).

Guardino Hub differs fundamentally from Marzban/PasarGuard:

  * **Auth**: ``POST /api/v1/auth/login`` (JSON username/password; optional 2FA).
    The bot logs in with the *reseller* (or super-admin) account. The resulting
    bearer token is cached in-process and refreshed on 401. 2FA must be OFF for
    the bot account (or an api-token used) — unattended re-login can't solve a
    TOTP challenge; we raise a clear error if the hub demands 2FA.
  * **Identity**: users are keyed by an integer ``user_id`` (+ ``label``), not a
    username. The neutral interface is username-typed, so id-based methods
    accept the **stringified user_id** in the ``username`` slot; ``create_user``
    returns it in ``PanelUser.remote_id`` (the bot stores it on
    ``Proxy.panel_user_id``).
  * **Units**: traffic is **GB**, duration is **days** (not bytes/seconds).
  * **Billing**: the hub owns pricing — ``quote`` / ``charged_amount`` /
    ``balance_after`` come back from the hub; the bot only adds resale margin.
    Day-pricing may be zero for some resellers — never assume it costs anything.
  * **Subscription**: a ``master_sub_token`` (hub master sub) plus per-node
    links from the underlying panels (PasarGuard/WireGuard/...). Which one to
    show the user is controlled by ``Server.link_policy``.

Guardino-only ops (renew/extend/add-traffic/change-nodes/quote/balance/links)
are exposed as extra methods used by the Guardino-aware purchase/manage paths.
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

logger = get_logger("panels/guardino")

_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
GIB = 1024**3  # bytes per GB used when mapping the hub's integer GB <-> bytes

# --- endpoints ---------------------------------------------------------------
_LOGIN = "/api/v1/auth/login"
_LOGIN_2FA = "/api/v1/auth/login/2fa"
_ME = "/api/v1/auth/me"
_USERS = "/api/v1/reseller/users"
_USER = "/api/v1/reseller/users/{id}"
_USER_OPS = "/api/v1/reseller/user-ops"
_QUOTE = "/api/v1/reseller/user-ops/quote"
_CATALOG = "/api/v1/reseller/catalog"


def _to_epoch(value: Any) -> Optional[int]:
    """Normalize an ISO datetime / int epoch / null to int epoch (or None)."""
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


class GuardinoPanel(BasePanel):
    panel_type = PanelType.guardino
    id_based = True
    panel_managed_billing = True

    def __init__(self, server) -> None:
        super().__init__(server)
        self._token: Optional[str] = server.token or None
        self._client: Optional[httpx.AsyncClient] = None
        self._label_ids: dict[str, int] = {}  # label -> hub user_id cache

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
        if not (self.server.username and self.server.password):
            raise PanelAuthError(
                "Guardino server has no stored credentials to (re)authenticate",
                server_id=self.server_id,
            )
        try:
            resp = await self._http().post(
                _LOGIN,
                json={"username": self.server.username, "password": self.server.password},
            )
        except httpx.HTTPError as exc:
            raise PanelError(str(exc), server_id=self.server_id) from exc
        if resp.status_code != 200:
            raise PanelAuthError(
                "Guardino login failed",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        data = resp.json()
        if data.get("requires_2fa"):
            raise PanelAuthError(
                "Guardino account requires 2FA; disable 2FA for the bot account "
                "or use an api-token",
                server_id=self.server_id,
            )
        token = data.get("access_token")
        if not token:
            raise PanelAuthError("Guardino returned no access_token", server_id=self.server_id)
        self._token = token
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Any = None,
        _retried: bool = False,
    ) -> httpx.Response:
        if not self._token:
            await self._authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = await self._http().request(
                method, path, json=json, params=params, headers=headers
            )
        except httpx.HTTPError as exc:
            raise PanelError(str(exc), server_id=self.server_id) from exc
        if resp.status_code == 401 and not _retried and self.server.password:
            await self._authenticate()
            return await self._request(
                method, path, json=json, params=params, _retried=True
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
            f"Guardino {resp.request.method} {resp.request.url.path} -> "
            f"{resp.status_code}: {detail}",
            status_code=resp.status_code,
        )

    @staticmethod
    def _try_int(ref: Any) -> Optional[int]:
        try:
            return int(ref)
        except (TypeError, ValueError):
            return None

    async def _resolve(self, ref: Any) -> int:
        """Resolve an identifier to the hub's integer user_id. A numeric ref is
        used directly; otherwise it's treated as a label and looked up via the
        list endpoint (cached). Raises PanelError(404) on no exact-label match —
        so the bot's data-plane can keep passing ``proxy.username`` (the label)
        and id-resolution stays inside the adapter."""
        n = self._try_int(ref)
        if n is not None:
            return n
        if ref in self._label_ids:
            return self._label_ids[ref]
        resp = await self._request("GET", _USERS, params={"q": ref, "limit": 50})
        self._ok(resp, allow=(200,))
        for item in resp.json().get("items", []):
            if item.get("label") == ref:
                uid = int(item["id"])
                self._label_ids[ref] = uid
                return uid
        raise PanelError(
            f"Guardino user with label {ref!r} not found",
            status_code=404,
            server_id=self.server_id,
        )

    @staticmethod
    def _gconfig(service: Any) -> dict:
        return getattr(service, "panel_config", None) or {}

    # -- parsing ---------------------------------------------------------------
    def _to_user(self, data: dict) -> PanelUser:
        """Map a Guardino UserOut to the neutral PanelUser."""
        total_gb = data.get("total_gb")
        return PanelUser(
            username=data.get("label", ""),
            status=_status(data.get("status")),
            used_traffic=int(data.get("used_bytes") or 0),
            data_limit=int(total_gb) * GIB if total_gb else None,
            expire=_to_epoch(data.get("expire_at")),
            remote_id=data.get("id"),
            raw=data,
        )

    # -- BasePanel impl --------------------------------------------------------
    async def get_admin(self) -> AdminInfo:
        resp = await self._request("GET", _ME)
        self._ok(resp, allow=(200,))
        data = resp.json()
        return AdminInfo(
            username=data.get("username", ""),
            is_sudo=str(data.get("role")) in ("admin", "owner", "super_admin"),
            raw=data,
        )

    async def get_inbounds(self) -> dict:
        """Guardino's provisioning catalog: nodes + pricing + presets.

        Returned shape (consumed by the admin service-builder):
            {"nodes": [{id,name,panel_type,price_per_gb}], "duration_presets",
             "traffic_options", "pricing", "policy", "balance"}
        """
        resp = await self._request("GET", _CATALOG)
        self._ok(resp, allow=(200,))
        data = resp.json()
        return {
            "nodes": [
                {
                    "id": n.get("id"),
                    "name": n.get("name"),
                    "panel_type": n.get("panel_type"),
                    "price_per_gb": n.get("price_per_gb"),
                }
                for n in data.get("nodes", [])
            ],
            "duration_presets": data.get("duration_presets", []),
            "traffic_options": data.get("traffic_options", []),
            "pricing": data.get("pricing", {}),
            "policy": data.get("policy", {}),
            "balance": data.get("balance"),
        }

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
        cfg = self._gconfig(service)
        total_gb = int(cfg.get("total_gb") or (data_limit // GIB if data_limit else 0))
        if total_gb <= 0:
            raise PanelError(
                "Guardino service needs a positive total_gb in panel_config",
                server_id=self.server_id,
            )
        days = int(cfg.get("days") or 0)
        if not days and expire:
            days = max(0, (int(expire) - int(datetime.now(timezone.utc).timestamp())) // 86400)

        body: dict[str, Any] = {
            "label": username,
            "total_gb": total_gb,
            "days": days,
            "pricing_mode": cfg.get("pricing_mode", "per_node"),
            "create_status": (PanelUserStatus(status).value if status else "active"),
        }
        if cfg.get("node_ids"):
            body["node_ids"] = [int(x) for x in cfg["node_ids"]]
        if cfg.get("node_group"):
            body["node_group"] = cfg["node_group"]
        if cfg.get("duration_preset"):
            body["duration_preset"] = cfg["duration_preset"]

        resp = await self._request("POST", _USER_OPS, json=body)
        self._ok(resp, allow=(200, 201))
        data = resp.json()
        # CreateUserResponse: user_id, label, master_sub_token, subscription_url,
        # expire_at, charged_amount, balance_after, nodes_provisioned.
        return PanelUser(
            username=data.get("label", username),
            status=PanelUserStatus.active,
            data_limit=total_gb * GIB,
            expire=_to_epoch(data.get("expire_at")),
            subscription_url=data.get("subscription_url") or "",
            remote_id=data.get("user_id"),
            raw=data,  # holds master_sub_token / charged_amount / balance_after
        )

    async def modify_user(self, username: str, params: ModifyUserParams) -> PanelUser:
        """Generic modify supports status changes (-> set-status). Volume/time
        changes don't map to a single Guardino call — use ``renew_user`` /
        ``add_traffic`` / ``extend`` instead (the Guardino purchase/manage path
        does)."""
        uid = await self._resolve(username)
        if params.is_set("status"):
            new = PanelUserStatus(params.status).value
            resp = await self._request(
                "POST",
                _USER.format(id=uid) + "/set-status",
                json={"status": "active" if new == "active" else "disabled"},
            )
            self._ok(resp, allow=(200,))
        if params.is_set("expire") or params.is_set("data_limit"):
            raise PanelError(
                "Guardino expire/data_limit changes must go through renew_user/"
                "add_traffic/extend, not modify_user",
                server_id=self.server_id,
            )
        user = await self.get_user(username)
        if user is None:
            raise PanelError("Guardino user vanished after modify", status_code=404)
        return user

    async def get_user(self, username: str) -> Optional[PanelUser]:
        try:
            uid = await self._resolve(username)
        except PanelError as exc:
            if exc.status_code == 404:
                return None
            raise
        resp = await self._request("GET", _USER.format(id=uid))
        if resp.status_code == 404:
            return None
        self._ok(resp, allow=(200,))
        user = self._to_user(resp.json())
        # Enrich with the subscription link(s) per link policy so the bot's
        # generic display/QR code (which reads subscription_url/links) works.
        try:
            links = await self._links_for(uid)
            user.subscription_url = links.get("primary") or ""
            user.links = list(links.get("node_urls") or [])
        except PanelError:
            pass
        return user

    async def get_users(self, usernames: list[str]) -> list[PanelUser]:
        """No batch-by-id endpoint; resolve + fetch each. For full reseller sync
        use the paginated list endpoint in the Guardino balance/sync job."""
        out: list[PanelUser] = []
        for ref in usernames or []:
            try:
                uid = await self._resolve(ref)
            except PanelError:
                continue
            resp = await self._request("GET", _USER.format(id=uid))
            if resp.status_code == 404:
                continue
            self._ok(resp, allow=(200,))
            out.append(self._to_user(resp.json()))
        return out

    async def remove_user(self, username: str) -> bool:
        uid = await self._resolve(username)
        resp = await self._request(
            "POST", _USER.format(id=uid) + "/refund", json={"action": "delete"}
        )
        if resp.status_code in (200, 204, 404):
            return True
        self._ok(resp)
        return True

    async def reset_usage(self, username: str) -> PanelUser:
        uid = await self._resolve(username)
        resp = await self._request("POST", _USER.format(id=uid) + "/reset-usage")
        self._ok(resp, allow=(200,))
        user = await self.get_user(username)
        if user is None:
            raise PanelError("Guardino user vanished after reset", status_code=404)
        return user

    async def revoke_subscription(self, username: str) -> PanelUser:
        uid = await self._resolve(username)
        resp = await self._request("POST", _USER.format(id=uid) + "/revoke")
        self._ok(resp, allow=(200,))
        user = await self.get_user(username)
        if user is None:
            raise PanelError("Guardino user vanished after revoke", status_code=404)
        return user

    async def service_modify_params(
        self, service: Any, existing: Optional[PanelUser] = None
    ) -> ModifyUserParams:
        # Node changes go through change_nodes explicitly; nothing to carry over.
        return ModifyUserParams()

    async def reset_proxy_credentials(self, username: str, service: Any) -> PanelUser:
        # Guardino has no "rotate proxy creds, keep sub" primitive; use revoke.
        raise PanelError(
            "Reset password is not supported on Guardino Hub; use revoke instead",
            server_id=self.server_id,
        )

    # -- Guardino-specific ops (used by the Guardino-aware paths) --------------
    async def quote(self, service: Any, *, label: str = "quote") -> dict:
        """Ask the hub what a (total_gb, days, nodes) plan would cost the
        reseller. Returns PriceQuoteResponse: {total_amount, per_node_amount,
        time_amount}. Use before create to pre-check balance. total_gb/days come
        from panel_config, falling back to the service's data_limit/
        expire_duration (same derivation as create_user)."""
        cfg = self._gconfig(service)
        data_limit = getattr(service, "data_limit", 0) or 0
        expire_duration = getattr(service, "expire_duration", 0) or 0
        body: dict[str, Any] = {
            "label": label,
            "total_gb": int(cfg.get("total_gb") or (data_limit // GIB)),
            "days": int(cfg.get("days") or (expire_duration // 86400)),
            "pricing_mode": cfg.get("pricing_mode", "per_node"),
        }
        if cfg.get("node_ids"):
            body["node_ids"] = [int(x) for x in cfg["node_ids"]]
        if cfg.get("node_group"):
            body["node_group"] = cfg["node_group"]
        resp = await self._request("POST", _QUOTE, json=body)
        self._ok(resp, allow=(200,))
        return resp.json()

    async def get_balance(self) -> int:
        """Current reseller wallet balance (toman) from the hub."""
        resp = await self._request("GET", _ME)
        self._ok(resp, allow=(200,))
        return int(resp.json().get("balance") or 0)

    async def renew_user(
        self, username: str, *, days: int, total_gb: int, pricing_mode: str = "bundle"
    ) -> dict:
        """Renew (reset+recharge) a user. Returns the hub OpResult (with
        charged_amount / new_balance)."""
        uid = await self._resolve(username)
        resp = await self._request(
            "POST",
            _USER.format(id=uid) + "/renew",
            json={"days": int(days), "total_gb": int(total_gb), "pricing_mode": pricing_mode},
        )
        self._ok(resp, allow=(200,))
        return resp.json()

    async def extend(self, username: str, days: int) -> dict:
        uid = await self._resolve(username)
        resp = await self._request(
            "POST", _USER.format(id=uid) + "/extend", json={"days": int(days)}
        )
        self._ok(resp, allow=(200,))
        return resp.json()

    async def add_traffic(self, username: str, add_gb: int) -> dict:
        uid = await self._resolve(username)
        resp = await self._request(
            "POST", _USER.format(id=uid) + "/add-traffic", json={"add_gb": int(add_gb)}
        )
        self._ok(resp, allow=(200,))
        return resp.json()

    async def change_nodes(
        self,
        username: str,
        *,
        add_node_ids: Optional[list[int]] = None,
        remove_node_ids: Optional[list[int]] = None,
    ) -> dict:
        uid = await self._resolve(username)
        body: dict[str, Any] = {}
        if add_node_ids:
            body["add_node_ids"] = [int(x) for x in add_node_ids]
        if remove_node_ids:
            body["remove_node_ids"] = [int(x) for x in remove_node_ids]
        resp = await self._request(
            "POST", _USER.format(id=uid) + "/change-nodes", json=body
        )
        self._ok(resp, allow=(200,))
        return resp.json()

    async def _links_for(self, uid: int, *, policy: Optional[str] = None) -> dict:
        """links endpoint + policy pick. Returns {primary, master_link,
        node_links, node_urls}."""
        resp = await self._request("GET", _USER.format(id=uid) + "/links")
        self._ok(resp, allow=(200,))
        data = resp.json()
        master = data.get("master_link")
        nodes = data.get("node_links") or []

        pol = policy or getattr(self.server, "link_policy", None)
        pol = str(getattr(pol, "value", pol) or "master_first")

        def _node_url(nl: dict) -> Optional[str]:
            return nl.get("full_url") or nl.get("direct_url") or nl.get("config_download_url")

        node_urls = [u for u in (_node_url(n) for n in nodes) if u]
        node_primary = node_urls[0] if node_urls else None
        primary = (node_primary or master) if pol == "node_first" else (master or node_primary)
        return {
            "primary": primary,
            "master_link": master,
            "node_links": nodes,
            "node_urls": node_urls,
        }

    async def get_links(self, username: str, *, policy: Optional[str] = None) -> dict:
        """Fetch subscription links and pick the primary one per link policy.
        The bot shows / QR-encodes ``primary``."""
        uid = await self._resolve(username)
        return await self._links_for(uid, policy=policy)


# --- one-shot helpers for the admin server-setup flow ------------------------
async def login(
    url: str,
    username: str,
    password: str,
    *,
    code: Optional[str] = None,
    challenge_token: Optional[str] = None,
) -> dict:
    """Log in to a Guardino hub. Without a 2FA code returns the raw
    TokenResponse (which may carry ``requires_2fa`` + ``challenge_token``);
    with ``challenge_token`` + ``code`` completes the 2FA step."""
    async with httpx.AsyncClient(base_url=url, timeout=_TIMEOUT) as client:
        if challenge_token and code:
            resp = await client.post(
                _LOGIN_2FA, json={"challenge_token": challenge_token, "code": code}
            )
        else:
            resp = await client.post(_LOGIN, json={"username": username, "password": password})
    if resp.status_code != 200:
        raise PanelAuthError("Guardino login failed", status_code=resp.status_code)
    return resp.json()


async def validate(url: str, token: str) -> AdminInfo:
    """Validate a Guardino bearer token and return the reseller identity."""
    async with httpx.AsyncClient(base_url=url, timeout=_TIMEOUT) as client:
        resp = await client.get(_ME, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise PanelAuthError("Guardino token validation failed", status_code=resp.status_code)
    data = resp.json()
    return AdminInfo(
        username=data.get("username", ""),
        is_sudo=str(data.get("role")) in ("admin", "owner", "super_admin"),
        raw=data,
    )
