from enum import Enum

from tortoise import fields

from app.utils.encryption import PasswordField

from . import TimedBase


class PanelType(str, Enum):
    """Which panel software a Server speaks to. Mirrors app.panels.base.PanelType
    (kept local so the models package stays independent of the panels layer).
    Default is ``marzban`` for backward compatibility with existing rows."""

    marzban = "marzban"
    pasarguard = "pasarguard"
    guardino = "guardino"


class Server(TimedBase):
    class Meta:
        table = "servers"

    id = fields.BigIntField(pk=True)
    host = fields.CharField(max_length=64, null=False)  # ip or domain
    port = fields.IntField(null=True)
    token = fields.CharField(max_length=512, null=False)
    https = fields.BooleanField(default=False)

    panel_type = fields.CharEnumField(
        PanelType, max_length=16, default=PanelType.marzban
    )

    name = fields.CharField(max_length=200, null=True)

    is_enabled = fields.BooleanField(default=True)

    total_proxies = fields.IntField(default=0)

    username = fields.CharField(max_length=34, null=True)
    password = PasswordField(null=True)

    @property
    def url(self) -> str:
        url = self.host.rstrip("/")
        if self.port:
            url = f"{url}:{self.port}"
        if self.https:
            return f"https://{url}"
        return f"http://{url}"

    @property
    def identifier(self) -> str:
        return self.name if self.name else self.host
