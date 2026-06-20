"""Marzban panel adapter.

Thin wrapper around the existing auto-generated ``marzban_client`` so the rest
of the bot can talk to Marzban through the neutral ``BasePanel`` interface.
Behavior is intentionally identical to the current direct usage — this adapter
only re-expresses it.
"""

from __future__ import annotations

from typing import Any, Optional

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
from marzban_client import AuthenticatedClient, Client
from marzban_client.api.admin import admin_token, get_current_admin
from marzban_client.api.system import get_inbounds
from marzban_client.api.user import (
    add_user,
    get_user,
    get_users,
    modify_user,
    remove_user,
    reset_user_data_usage,
    revoke_user_subscription,
)
from marzban_client.errors import UnexpectedStatus
from marzban_client.models.body_admin_token_api_admin_token_post import (
    BodyAdminTokenApiAdminTokenPost,
)
from marzban_client.models.user_create import UserCreate
from marzban_client.models.user_create_inbounds import UserCreateInbounds
from marzban_client.models.user_create_proxies import UserCreateProxies
from marzban_client.models.user_data_limit_reset_strategy import (
    UserDataLimitResetStrategy,
)
from marzban_client.models.user_modify import UserModify, UserStatusModify
from marzban_client.models.user_modify_inbounds import UserModifyInbounds
from marzban_client.models.user_modify_proxies import UserModifyProxies
from marzban_client.models.user_status import UserStatus

logger = get_logger("panels/marzban")


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _additional(obj: Any) -> dict:
    """Extract the dict from a generated *Inbounds/*Proxies model, defensively."""
    if obj is None:
        return {}
    if hasattr(obj, "additional_properties"):
        return dict(obj.additional_properties)
    if isinstance(obj, dict):
        return obj
    return {}


def _reset_strategy(value: Any) -> UserDataLimitResetStrategy:
    try:
        return UserDataLimitResetStrategy(_enum_value(value) or "no_reset")
    except ValueError:
        return UserDataLimitResetStrategy.NO_RESET


class MarzbanPanel(BasePanel):
    panel_type = PanelType.marzban

    def __init__(self, server) -> None:
        super().__init__(server)
        self._client: Optional[AuthenticatedClient] = None

    def _c(self) -> AuthenticatedClient:
        if self._client is None:
            self._client = AuthenticatedClient(
                base_url=self.server.url,
                token=self.server.token,
                raise_on_unexpected_status=True,
            )
        return self._client

    # -- parsing ---------------------------------------------------------------
    def _to_user(self, data: Any) -> PanelUser:
        status_val = _enum_value(getattr(data, "status", "active")) or "active"
        try:
            status = PanelUserStatus(status_val)
        except ValueError:
            status = PanelUserStatus.active
        return PanelUser(
            username=getattr(data, "username", "") or "",
            status=status,
            used_traffic=int(getattr(data, "used_traffic", 0) or 0),
            lifetime_used_traffic=int(getattr(data, "lifetime_used_traffic", 0) or 0),
            data_limit=getattr(data, "data_limit", None) or None,
            expire=getattr(data, "expire", None) or None,
            data_limit_reset_strategy=str(
                _enum_value(getattr(data, "data_limit_reset_strategy", "no_reset"))
                or "no_reset"
            ),
            subscription_url=getattr(data, "subscription_url", "") or "",
            links=list(getattr(data, "links", []) or []),
            inbounds=_additional(getattr(data, "inbounds", None)),
            proxies=_additional(getattr(data, "proxies", None)),
            raw=data.to_dict() if hasattr(data, "to_dict") else None,
        )

    # -- BasePanel impl --------------------------------------------------------
    async def get_admin(self) -> AdminInfo:
        try:
            resp = await get_current_admin.asyncio_detailed(client=self._c())
        except UnexpectedStatus as exc:
            raise PanelAuthError(
                str(exc), status_code=exc.status_code, server_id=self.server_id
            ) from exc
        if resp.status_code != 200 or resp.parsed is None:
            raise PanelAuthError(
                "Marzban admin validation failed",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        return AdminInfo(
            username=resp.parsed.username,
            is_sudo=bool(getattr(resp.parsed, "is_sudo", False)),
        )

    async def get_inbounds(self) -> dict:
        try:
            result = await get_inbounds.asyncio(client=self._c())
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        return {
            protocol: [inbound.tag for inbound in inbounds]
            for protocol, inbounds in result.additional_properties.items()
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
        if getattr(service, "all_inbounds", False):
            inbounds = await self.get_inbounds()
        else:
            inbounds = service.inbounds
        proxies = {
            protocol: service.create_proxy_protocols(protocol) for protocol in inbounds
        }
        kwargs: dict[str, Any] = dict(
            username=username,
            proxies=UserCreateProxies.from_dict(proxies),
            inbounds=UserCreateInbounds.from_dict(inbounds),
            data_limit=int(data_limit or 0),
            data_limit_reset_strategy=_reset_strategy(data_limit_reset_strategy),
        )
        if status is not None:
            kwargs["status"] = UserStatus(PanelUserStatus(status).value)
        if expire is not None:
            kwargs["expire"] = int(expire)
        if on_hold_expire_duration is not None:
            kwargs["on_hold_expire_duration"] = int(on_hold_expire_duration)
        if on_hold_timeout is not None:
            # Marzban's client serializes a datetime to ISO itself; pass through.
            kwargs["on_hold_timeout"] = on_hold_timeout

        try:
            resp = await add_user.asyncio_detailed(client=self._c(), body=UserCreate(**kwargs))
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp.status_code not in (200, 201) or resp.parsed is None:
            raise PanelError(
                f"Marzban create_user -> {resp.status_code}",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        return self._to_user(resp.parsed)

    async def modify_user(self, username: str, params: ModifyUserParams) -> PanelUser:
        body = UserModify()
        if params.is_set("status"):
            body.status = UserStatusModify(PanelUserStatus(params.status).value)
        if params.is_set("expire"):
            body.expire = params.expire
        if params.is_set("data_limit"):
            body.data_limit = params.data_limit
        if params.is_set("data_limit_reset_strategy"):
            body.data_limit_reset_strategy = _reset_strategy(params.data_limit_reset_strategy)
        if params.is_set("inbounds"):
            body.inbounds = UserModifyInbounds.from_dict(params.inbounds or {})
        if params.is_set("proxies"):
            body.proxies = UserModifyProxies.from_dict(params.proxies or {})
        if params.is_set("note"):
            body.note = params.note

        try:
            resp = await modify_user.asyncio_detailed(username, client=self._c(), body=body)
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp.status_code != 200 or resp.parsed is None:
            raise PanelError(
                f"Marzban modify_user -> {resp.status_code}",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        return self._to_user(resp.parsed)

    async def get_user(self, username: str) -> Optional[PanelUser]:
        try:
            resp = await get_user.asyncio_detailed(username, client=self._c())
        except UnexpectedStatus as exc:
            if exc.status_code == 404:
                return None
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp.status_code == 404:
            return None
        if resp.parsed is None:
            raise PanelError(
                f"Marzban get_user -> {resp.status_code}",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        return self._to_user(resp.parsed)

    async def get_users(self, usernames: list[str]) -> list[PanelUser]:
        if not usernames:
            return []
        try:
            resp = await get_users.asyncio_detailed(client=self._c(), username=usernames)
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp.parsed is None:
            return []
        return [self._to_user(u) for u in resp.parsed.users]

    async def remove_user(self, username: str) -> bool:
        try:
            await remove_user.asyncio(username, client=self._c())
        except UnexpectedStatus as exc:
            if exc.status_code == 404:
                return True
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        return True

    async def reset_usage(self, username: str) -> PanelUser:
        try:
            resp = await reset_user_data_usage.asyncio_detailed(username, client=self._c())
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp.status_code != 200 or resp.parsed is None:
            raise PanelError(
                f"Marzban reset_usage -> {resp.status_code}",
                status_code=resp.status_code,
                server_id=self.server_id,
            )
        return self._to_user(resp.parsed)

    async def service_modify_params(
        self, service: Any, existing: Optional[PanelUser] = None
    ) -> ModifyUserParams:
        if getattr(service, "all_inbounds", False):
            inbounds = await self.get_inbounds()
        else:
            inbounds = service.inbounds
        existing_proxies = existing.proxies if existing else {}
        proxies: dict = {}
        for protocol in inbounds:
            if protocol in existing_proxies:
                # carry over existing protocol settings (preserve UUID/password)
                proxies[protocol] = existing_proxies[protocol]
            else:
                proxies[protocol] = service.create_proxy_protocols(protocol)
        return ModifyUserParams(inbounds=inbounds, proxies=proxies)

    async def reset_proxy_credentials(self, username: str, service: Any) -> PanelUser:
        existing = await self.get_user(username)
        if existing is None:
            raise PanelError(
                "user not found", status_code=404, server_id=self.server_id
            )
        # Fresh protocol settings -> Marzban regenerates UUID/password.
        proxies = {
            protocol: service.create_proxy_protocols(protocol)
            for protocol in existing.proxies
        }
        return await self.modify_user(username, ModifyUserParams(proxies=proxies))

    async def revoke_subscription(self, username: str) -> PanelUser:
        try:
            resp = await revoke_user_subscription.asyncio(username, client=self._c())
        except UnexpectedStatus as exc:
            raise PanelError(str(exc), status_code=exc.status_code, server_id=self.server_id) from exc
        if resp is None:
            raise PanelError("Marzban revoke_subscription returned nothing", server_id=self.server_id)
        return self._to_user(resp)


async def fetch_token(url: str, username: str, password: str) -> str:
    """One-shot admin token exchange (server-setup flow)."""
    async with Client(url, raise_on_unexpected_status=True) as client:
        try:
            resp = await admin_token.asyncio(
                client=client,
                body=BodyAdminTokenApiAdminTokenPost(username=username, password=password),
            )
        except UnexpectedStatus as exc:
            raise PanelAuthError(str(exc), status_code=exc.status_code) from exc
    if resp is None or not getattr(resp, "access_token", None):
        raise PanelAuthError("Marzban returned no access_token")
    return resp.access_token


async def validate_token(url: str, token: str) -> AdminInfo:
    """Validate a Marzban admin token and return identity."""
    async with AuthenticatedClient(url, token=token, raise_on_unexpected_status=True) as client:
        try:
            resp = await get_current_admin.asyncio_detailed(client=client)
        except UnexpectedStatus as exc:
            raise PanelAuthError(str(exc), status_code=exc.status_code) from exc
    if resp.status_code != 200 or resp.parsed is None:
        raise PanelAuthError("Marzban admin validation failed", status_code=resp.status_code)
    return AdminInfo(
        username=resp.parsed.username, is_sudo=bool(getattr(resp.parsed, "is_sudo", False))
    )
