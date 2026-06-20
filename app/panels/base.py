"""Neutral panel interface + DTOs shared by all panel adapters.

The goal is that handlers/jobs/services depend ONLY on this module, never on a
panel-specific client. Each concrete adapter (Marzban, PasarGuard, Guardino)
maps these neutral types to/from its native API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.models.server import Server


class PanelType(str, Enum):
    """Supported panel kinds. Value is stored on Server.panel_type."""

    marzban = "marzban"
    pasarguard = "pasarguard"
    guardino = "guardino"


class PanelUserStatus(str, Enum):
    """Neutral user status. Values intentionally match Marzban/PasarGuard
    UserStatus *and* the internal models.proxy.ProxyStatus values, so mapping
    in either direction is a no-op string compare."""

    active = "active"
    disabled = "disabled"
    limited = "limited"
    expired = "expired"
    on_hold = "on_hold"


class _Unset:
    """Sentinel for ModifyUserParams: 'leave this field untouched'.

    Distinct from None, which is a meaningful value for some panel fields
    (e.g. expire=None / data_limit=None meaning 'unlimited' or 'no change'
    depending on panel). Adapters apply a field only when it is not UNSET.
    """

    _instance: Optional["_Unset"] = None

    def __new__(cls) -> "_Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET: Any = _Unset()


class PanelError(Exception):
    """Adapter-level error. Wraps transport / unexpected-status failures so
    callers can catch one type regardless of the underlying panel client.

    status_code is the HTTP status when known (else None)."""

    def __init__(
        self,
        message: str = "",
        *,
        status_code: Optional[int] = None,
        server_id: Optional[int] = None,
    ) -> None:
        self.status_code = status_code
        self.server_id = server_id
        super().__init__(message)


class PanelAuthError(PanelError):
    """Authentication / token acquisition failed (401/403 or bad credentials)."""


@dataclass
class AdminInfo:
    """Neutral admin identity returned by auth / token validation."""

    username: str
    is_sudo: bool = False
    raw: Optional[dict] = None


@dataclass
class PanelUser:
    """Neutral snapshot of a remote panel user.

    Common read fields are normalized across panels:
      - expire: epoch seconds (int) or None for unlimited / not-set.
      - data_limit / used_traffic / lifetime_used_traffic: bytes (int).
      - status: PanelUserStatus.

    Provisioning fields are panel-shaped and used mostly to *carry over*
    existing config on renew/modify; not all panels populate all of them:
      - inbounds: Marzban dict {protocol: [tags]}.
      - proxies: Marzban {protocol: {settings}} / PasarGuard proxy_settings.
      - group_ids: PasarGuard group ids.
    """

    username: str
    status: PanelUserStatus = PanelUserStatus.active
    used_traffic: int = 0
    lifetime_used_traffic: int = 0
    data_limit: Optional[int] = None
    expire: Optional[int] = None
    data_limit_reset_strategy: str = "no_reset"
    subscription_url: str = ""
    links: list[str] = field(default_factory=list)
    inbounds: dict = field(default_factory=dict)
    proxies: dict = field(default_factory=dict)
    group_ids: list[int] = field(default_factory=list)
    # Panel-native identifier when it is NOT the username (e.g. Guardino user_id).
    remote_id: Optional[int] = None
    raw: Optional[dict] = None


@dataclass
class ModifyUserParams:
    """Partial update spec. Every field defaults to UNSET = 'don't touch'.

    Provisioning (inbounds/proxies/group_ids) is normally derived by the
    adapter from a Service; pass the resolved values here only when the caller
    already computed them (e.g. carry-over logic in bulk jobs)."""

    status: Any = UNSET  # PanelUserStatus | str
    expire: Any = UNSET  # int epoch | 0 (unlimited) | None
    data_limit: Any = UNSET  # int bytes | 0 (unlimited)
    data_limit_reset_strategy: Any = UNSET  # str
    inbounds: Any = UNSET  # dict
    proxies: Any = UNSET  # dict
    group_ids: Any = UNSET  # list[int]
    note: Any = UNSET  # str

    def is_set(self, name: str) -> bool:
        return getattr(self, name) is not UNSET


class BasePanel(ABC):
    """Abstract panel adapter. One instance is bound to one Server.

    Concrete adapters own their own client/session lifecycle and token refresh.
    All methods raise PanelError (or PanelAuthError) on failure; callers should
    not need to know the underlying client's exception types.
    """

    panel_type: PanelType

    #: Whether this panel provisions via PasarGuard-style group ids.
    uses_groups: bool = False
    #: Whether the panel keys users by an integer id rather than username
    #: (True for Guardino Hub).
    id_based: bool = False
    #: Whether pricing/billing is owned by the panel itself (Guardino Hub),
    #: rather than computed by the bot.
    panel_managed_billing: bool = False

    def __init__(self, server: "Server") -> None:
        self.server = server
        self.server_id = server.id

    # -- identity / validation -------------------------------------------------
    @abstractmethod
    async def get_admin(self) -> AdminInfo:
        """Return the authenticated admin's identity (used to validate a server
        connection). Raises PanelAuthError on bad/expired credentials."""

    # -- network / provisioning catalog ---------------------------------------
    @abstractmethod
    async def get_inbounds(self) -> dict:
        """Return the panel's provisioning catalog.

        Marzban: {protocol: [inbound_tag, ...]}.
        PasarGuard: {"groups": [{"id", "name", "inbound_tags"}], ...} plus a
        flat {protocol: [tags]} view for UI compatibility where possible.
        """

    # -- user CRUD -------------------------------------------------------------
    @abstractmethod
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
        """Create a user, building native provisioning from `service`
        (service.panel_config / inbounds / flow). Raises PanelError; 409 on
        duplicate username is surfaced via PanelError.status_code == 409."""

    @abstractmethod
    async def modify_user(self, username: str, params: ModifyUserParams) -> PanelUser:
        """Apply a partial update. Only fields not UNSET are changed."""

    @abstractmethod
    async def get_user(self, username: str) -> Optional[PanelUser]:
        """Fetch one user, or None if 404."""

    @abstractmethod
    async def get_users(self, usernames: list[str]) -> list[PanelUser]:
        """Batch fetch. Empty list yields empty list (no full-table scan)."""

    @abstractmethod
    async def remove_user(self, username: str) -> bool:
        """Delete a user. Returns True on success / already-gone (404)."""

    @abstractmethod
    async def reset_usage(self, username: str) -> PanelUser:
        """Reset the user's used traffic to zero."""

    @abstractmethod
    async def revoke_subscription(self, username: str) -> PanelUser:
        """Rotate the user's subscription token / proxy credentials."""

    # -- provisioning helpers --------------------------------------------------
    async def service_modify_params(
        self, service: Any, existing: Optional[PanelUser] = None
    ) -> ModifyUserParams:
        """Build ONLY the network-provisioning portion of a modify for a
        Service, panel-shaped:

          * Marzban  -> inbounds + proxies (carries over `existing` proxy
            settings so UUIDs/passwords survive a renew/re-apply);
          * PasarGuard -> group_ids (proxy_settings left untouched).

        Callers (renew, bulk re-apply) then set expire/data_limit/reset on the
        returned params and call ``modify_user`` — staying panel-agnostic.
        """
        raise NotImplementedError

    async def reset_proxy_credentials(
        self, username: str, service: Any
    ) -> PanelUser:
        """Regenerate the user's proxy credentials (UUID/password) while
        preserving the subscription token (the 'reset password' action).
        Marzban: re-provision protocols fresh. PasarGuard: not supported yet."""
        raise NotImplementedError

    # -- convenience -----------------------------------------------------------
    async def set_status(self, username: str, status: PanelUserStatus) -> PanelUser:
        """Enable/disable shortcut over modify_user."""
        return await self.modify_user(username, ModifyUserParams(status=status))

    async def aclose(self) -> None:
        """Release any held transport resources. Default no-op."""
        return None
