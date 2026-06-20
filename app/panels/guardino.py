"""Guardino Hub panel adapter — PHASE 2 placeholder.

Guardino Hub differs fundamentally from Marzban/PasarGuard:
  * auth via ``/api/v1/auth/login`` (JSON username/password, optional 2FA,
    api-tokens) rather than an OAuth2 admin token;
  * users are keyed by integer ``user_id`` (+ ``label``), not username;
  * traffic is in **GB** and duration in **days** (not bytes/seconds);
  * pricing/billing is owned by the hub (``quote``/``charged_amount``/
    ``balance_after``) — the bot only adds its resale margin;
  * provisioning targets **node_ids**, and ops are extend/renew/add-traffic/
    decrease-time/change-nodes/refund/set-status/reset-usage/revoke.

This is implemented after PasarGuard support is complete. The class exists so
the registry import resolves; instantiating it before implementation raises a
clear error instead of failing obscurely.
"""

from __future__ import annotations

from app.panels.base import BasePanel, PanelType


class GuardinoPanel(BasePanel):
    panel_type = PanelType.guardino
    id_based = True
    panel_managed_billing = True

    def __init__(self, server) -> None:  # pragma: no cover - phase 2
        raise NotImplementedError(
            "Guardino Hub adapter is not implemented yet (phase 2). "
            "Configure this server as Marzban or PasarGuard for now."
        )

    async def get_admin(self):  # pragma: no cover
        raise NotImplementedError

    async def get_inbounds(self):  # pragma: no cover
        raise NotImplementedError

    async def create_user(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def modify_user(self, username, params):  # pragma: no cover
        raise NotImplementedError

    async def get_user(self, username):  # pragma: no cover
        raise NotImplementedError

    async def get_users(self, usernames):  # pragma: no cover
        raise NotImplementedError

    async def remove_user(self, username):  # pragma: no cover
        raise NotImplementedError

    async def reset_usage(self, username):  # pragma: no cover
        raise NotImplementedError

    async def revoke_subscription(self, username):  # pragma: no cover
        raise NotImplementedError
