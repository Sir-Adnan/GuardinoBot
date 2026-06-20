"""Panel registry: resolve a Server to its concrete adapter, with caching.

Replaces the role of ``app.marzban.Marzban`` for multi-panel use. The legacy
``Marzban`` registry stays for backward compatibility while call sites migrate.

``Server.panel_type`` does not exist until its migration lands; resolution is
defensive and defaults to Marzban so behavior is unchanged pre-migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.logger import get_logger
from app.panels.base import BasePanel, PanelType

if TYPE_CHECKING:
    from app.models.server import Server

logger = get_logger("panels/registry")


def _resolve_type(server: "Server") -> PanelType:
    raw = getattr(server, "panel_type", None)
    if raw is None:
        return PanelType.marzban
    if isinstance(raw, PanelType):
        return raw
    try:
        return PanelType(getattr(raw, "value", raw))
    except ValueError:
        logger.warning("Unknown panel_type %r for server %s; defaulting to marzban", raw, server.id)
        return PanelType.marzban


def build_panel(server: "Server") -> BasePanel:
    """Construct a fresh adapter for a Server (not cached)."""
    panel_type = _resolve_type(server)
    # Imported lazily to avoid importing every panel client at module load.
    if panel_type is PanelType.pasarguard:
        from app.panels.pasarguard import PasarGuardPanel

        return PasarGuardPanel(server)
    if panel_type is PanelType.guardino:
        from app.panels.guardino import GuardinoPanel  # noqa: F401 - added in phase 2

        return GuardinoPanel(server)
    from app.panels.marzban import MarzbanPanel

    return MarzbanPanel(server)


class PanelRegistry:
    """Process-wide cache of adapter instances keyed by server id."""

    _instances: dict[int, BasePanel] = {}

    @classmethod
    async def refresh(cls) -> None:
        """Rebuild all adapters from DB. Closes previous transports."""
        from app.models.server import Server

        await cls.aclose_all()
        servers = await Server.all()
        cls._instances = {server.id: build_panel(server) for server in servers}

    @classmethod
    def get(cls, server_id: int) -> BasePanel:
        panel = cls._instances.get(server_id)
        if panel is None:
            raise KeyError(f"No panel adapter for server id {server_id!r}")
        return panel

    @classmethod
    def try_get(cls, server_id: int) -> Optional[BasePanel]:
        return cls._instances.get(server_id)

    @classmethod
    def set(cls, server: "Server") -> BasePanel:
        """Build + cache (or replace) the adapter for a single server."""
        panel = build_panel(server)
        cls._instances[server.id] = panel
        return panel

    @classmethod
    async def aclose_all(cls) -> None:
        for panel in cls._instances.values():
            try:
                await panel.aclose()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
        cls._instances.clear()


def get_panel(server_id: int) -> BasePanel:
    """Module-level shortcut mirroring ``Marzban.get_server``."""
    return PanelRegistry.get(server_id)
