"""Panel adapter layer.

Abstracts the differences between supported VPN panels (Marzban, PasarGuard,
Guardino Hub) behind a single neutral interface so the rest of the bot never
talks to a panel-specific client directly.

Public surface:
    PanelType            -- enum of supported panels (mirrors Server.panel_type)
    PanelUserStatus      -- neutral user status (active/disabled/limited/expired/on_hold)
    PanelUser            -- neutral representation of a remote panel user
    AdminInfo            -- neutral admin identity returned on auth/validation
    ModifyUserParams     -- partial-update spec for modify_user (UNSET-aware)
    UNSET                -- sentinel meaning "do not touch this field"
    BasePanel            -- abstract adapter interface
    PanelError           -- adapter-level error wrapper
    get_panel            -- registry lookup by server id
    build_panel          -- build an adapter instance for a Server
"""

from .base import (
    UNSET,
    AdminInfo,
    BasePanel,
    ModifyUserParams,
    PanelError,
    PanelUser,
    PanelUserStatus,
    PanelType,
)
from .registry import PanelRegistry, build_panel, get_panel

__all__ = [
    "UNSET",
    "AdminInfo",
    "BasePanel",
    "ModifyUserParams",
    "PanelError",
    "PanelUser",
    "PanelUserStatus",
    "PanelType",
    "PanelRegistry",
    "build_panel",
    "get_panel",
]
