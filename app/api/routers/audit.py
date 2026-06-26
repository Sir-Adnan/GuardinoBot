"""Audit log — append-only record of every state-changing admin/reseller/
super-admin action across the bot and the web panel.

Read-only oversight tool, **super-admin only**: it exposes who did what (incl.
other admins/resellers), so it is intentionally not visible to resellers.
"""

from datetime import datetime as dt
from datetime import timedelta as td
from typing import Optional

from fastapi import APIRouter, Depends, Query
from tortoise.expressions import Q

from app.api.deps import require_role
from app.api.schemas import ROLE_NAMES, AuditListItem, AuditPage
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])


def _item(a: AuditLog) -> AuditListItem:
    actor = a.actor if a.actor_id else None
    return AuditListItem(
        id=a.id,
        action=a.action,
        source=str(getattr(a.source, "value", a.source)),
        actor_id=a.actor_id,
        actor_name=(actor.username or actor.name) if actor else None,
        actor_role=a.actor_role,
        actor_role_name=ROLE_NAMES.get(a.actor_role, str(a.actor_role)),
        target_type=a.target_type,
        target_id=a.target_id,
        target_label=a.target_label,
        amount=a.amount,
        detail=a.detail,
        created_at=a.created_at,
    )


@router.get("", response_model=AuditPage)
async def list_audit(
    _: User = Depends(require_role(User.Role.super_user)),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    action: Optional[str] = None,
    source: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    search: Optional[str] = None,
    start: Optional[str] = None,  # ISO date — created_at >= start
    end: Optional[str] = None,  # ISO date — created_at <= end (inclusive day)
) -> AuditPage:
    q = AuditLog.all().prefetch_related("actor")
    if action:
        q = q.filter(action__icontains=action.strip())
    if source:
        q = q.filter(source=source)
    if actor_id:
        q = q.filter(actor_id=actor_id)
    if target_type:
        q = q.filter(target_type=target_type)
    if target_id:
        q = q.filter(target_id=str(target_id))
    if start:
        try:
            q = q.filter(created_at__gte=dt.fromisoformat(start))
        except ValueError:
            pass
    if end:
        try:
            q = q.filter(created_at__lt=dt.fromisoformat(end) + td(days=1))
        except ValueError:
            pass
    if search:
        s = search.strip()
        q = q.filter(Q(target_label__icontains=s) | Q(action__icontains=s))
    total = await q.count()
    rows = await q.order_by("-id").offset((page - 1) * per_page).limit(per_page)
    return AuditPage(items=[_item(a) for a in rows], total=total)
