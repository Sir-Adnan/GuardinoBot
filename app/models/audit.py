from enum import Enum
from typing import TYPE_CHECKING

from tortoise import fields

from app.models import CreatedTimeBase

if TYPE_CHECKING:
    from .user import User


class AuditLog(CreatedTimeBase):
    """Append-only record of every state-changing admin/reseller/super-admin
    action across the bot and the web panel.

    Exists to detect financial abuse: when the bot is installed for a
    third-party super-admin who is connected to the owner's PasarGuard/Guardino
    panel, every management action (revoke, reset-usage, delete, balance change,
    panel toggle, settings change, ...) must leave a trail. Rows are never
    edited or deleted by application code.
    """

    class Meta:
        table = "audit_logs"
        ordering = ["-id"]

    class Source(str, Enum):
        web = "web"
        bot = "bot"
        system = "system"

    id = fields.IntField(pk=True)

    # Who did it. actor_role is a snapshot taken at action time, because a
    # user's role can change later and the log must reflect the role then.
    actor: fields.ForeignKeyNullableRelation["User"] = fields.ForeignKeyField(
        "models.User",
        "audit_logs",
        on_delete=fields.SET_NULL,
        null=True,
    )
    actor_role = fields.IntField(default=0)

    source = fields.CharEnumField(Source, max_length=8, default=Source.web)
    action = fields.CharField(max_length=64, null=False)  # e.g. "proxy.revoke"

    # Free-form target so one table covers proxy/user/service/server/setting/...
    target_type = fields.CharField(max_length=32, null=True)
    target_id = fields.CharField(max_length=64, null=True)
    target_label = fields.CharField(max_length=128, null=True)

    # Amount (toman) for financially-relevant actions; summable in reports.
    amount = fields.FloatField(null=True)

    # before/after snapshot + extra context. NEVER store secrets/tokens here.
    detail = fields.JSONField(null=True)
