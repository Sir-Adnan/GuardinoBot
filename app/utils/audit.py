"""Append-only audit logging shared by the bot and the web API.

Records every state-changing admin/reseller/super-admin action so that
financial abuse (e.g. a third-party super-admin provisioning free
subscriptions on the owner's panel) leaves a trail.

Importable from the FastAPI process: it depends only on the model layer and
must never reach into ``app.main`` (which would pull the whole bot runtime).
"""

import logging
from typing import Any, Optional

from app.models.audit import AuditLog
from app.models.user import User

logger = logging.getLogger("audit")


async def record_audit(
    *,
    action: str,
    actor: Optional[User] = None,
    source: str = AuditLog.Source.web,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    target_label: Optional[str] = None,
    amount: Optional[float] = None,
    detail: Optional[dict] = None,
) -> None:
    """Write one audit row. Best-effort: a logging failure must never break the
    underlying action, so all errors are swallowed (and logged locally)."""
    try:
        await AuditLog.create(
            actor=actor,
            actor_role=int(getattr(actor, "role", 0) or 0),
            source=source,
            action=action,
            target_type=target_type,
            target_id=None if target_id is None else str(target_id),
            target_label=target_label,
            amount=amount,
            detail=detail,
        )
    except Exception as exc:  # pragma: no cover - audit must not raise
        logger.error("record_audit failed for action=%s: %s", action, exc)
