from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.server import Server

from . import admin


class ServersAction(str, Enum):
    show = "show"
    add_server = "add_server"


class Servers(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="servers"):
        server_id: int = 0
        action: ServersAction

    def __init__(self, servers: list[Server], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for server in servers:
            self.button(
                text=f"{server.name} | {server.host}",
                callback_data=self.Callback(
                    server_id=server.id, action=ServersAction.show
                ),
            )
        self.button(
            text="افزودن سرور",
            callback_data=self.Callback(action=ServersAction.add_server),
        )
        self.button(
            text="برگشت",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.panel
            ),
        )
        self.adjust(1, 1)


class ServerActAction(str, Enum):
    rem = "rem"
    disable = "disable"
    enable = "enable"
    broadcast = "broadcast"
    change_price = "change_price"
    bulk_update = "bulk_update"
    edit = "edit"
    ping = "ping"


class ServerAct(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="srvact"):
        server_id: int
        action: ServerActAction
        confirmed: bool = False

    def __init__(self, server: Server, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="حذف سرور",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.rem
            ),
        )
        if server.is_enabled:
            self.button(
                text="غیرفعال سازی",
                callback_data=self.Callback(
                    server_id=server.id, action=ServerActAction.disable
                ),
            )
        else:
            self.button(
                text="فعال سازی",
                callback_data=self.Callback(
                    server_id=server.id, action=ServerActAction.enable
                ),
            )
        self.button(
            text="ویرایش سرور",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.edit
            ),
        )
        self.button(
            text="Ping",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.ping
            ),
        )
        self.button(
            text="پیام همگانی به کاربران این سرور",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.broadcast
            ),
        )
        self.button(
            text="کاهش/افزایش قیمت سرویس‌ها",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.change_price
            ),
        )
        self.button(
            text="ویرایش همگانی اشتراک‌ها",
            callback_data=self.Callback(
                server_id=server.id, action=ServerActAction.bulk_update
            ),
        )
        self.button(
            text="برگشت", callback_data=admin.AdminPanel.Callback(action="servers")
        )
        self.adjust(1, 2, 1, 1)


class ConfirmServerAction(InlineKeyboardBuilder):
    def __init__(
        self, server: Server, action: ServerActAction, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.button(
            text="تایید",
            callback_data=ServerAct.Callback(
                server_id=server.id, action=action, confirmed=True
            ),
        )
        self.button(
            text="برگشت",
            callback_data=Servers.Callback(
                server_id=server.id, action=ServersAction.show
            ),
        )


class EditServerAction(str, Enum):
    host = "edit_host"
    port = "edit_port"
    token = "edit_token"
    name = "edit_name"
    https = "https"
    save = "save"


class EditServer(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="editsrv"):
        server_id: int
        action: EditServerAction

    def __init__(self, server: Server, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for action in EditServerAction:
            if not action.value.startswith("edit_"):
                continue
            self.button(
                text=f"ویرایش {action.name.capitalize()}",
                callback_data=self.Callback(server_id=server.id, action=action),
            )
        self.button(
            text="flip HTTPS",
            callback_data=self.Callback(
                server_id=server.id, action=EditServerAction.https
            ),
        )
        self.button(
            text="ذخیره",
            callback_data=self.Callback(
                server_id=server.id, action=EditServerAction.save
            ),
        )
        self.button(
            text="لغو",
            callback_data=Servers.Callback(
                server_id=server.id, action=ServersAction.show
            ),
        )
        self.adjust(2, 2, 1, 1)


class BulkUpdateServicesProc(str, Enum):
    percent = "percent"
    toman = "toman"
    inc = "inc"
    dec = "dec"
    enter_value = "enter_value"

    proceed = "proceed"


class BulkUpdateServices(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="srvsbulkup"):
        field: Literal["percent", "toman"] | None = None
        action: Literal["inc", "dec"] | None = None
        value: int | None = None
        proc: BulkUpdateServicesProc
        server_id: int | None = None

    def __init__(
        self,
        field: Literal["percent", "toman"],
        action: Literal["inc", "dec"],
        value: int | None,
        server_id: int | None = None,
        proceed_button: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="قیمت بر چه اساسی تغییر کند؟",
            callback_data="ph",
        )
        self.button(
            text=f"درصد {'✅' if field == 'percent' else ''}",
            callback_data=self.Callback(
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateServicesProc.percent,
                server_id=server_id,
            ),
        )
        self.button(
            text=f"مبلغ به تومان {'✅' if field == 'toman' else ''}",
            callback_data=self.Callback(
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateServicesProc.toman,
                server_id=server_id,
            ),
        )
        self.button(
            text="چه عملیاتی انجام شود؟",
            callback_data="ph",
        )
        self.button(
            text=f"افزایش {'✅' if action == 'inc' else ''}",
            callback_data=self.Callback(
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateServicesProc.inc,
                server_id=server_id,
            ),
        )
        self.button(
            text=f"کاهش {'✅' if action == 'dec' else ''}",
            callback_data=self.Callback(
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateServicesProc.dec,
                server_id=server_id,
            ),
        )
        self.button(
            text="وارد کردن مقدار",
            callback_data=self.Callback(
                field=field,
                action=action,
                value=value,
                proc=BulkUpdateServicesProc.enter_value,
                server_id=server_id,
            ),
        )
        if proceed_button:
            self.button(
                text="⚠️ اجرای دستور ⚠️",
                callback_data=self.Callback(
                    field=field,
                    action=action,
                    value=value,
                    proc=BulkUpdateServicesProc.proceed,
                    server_id=server_id,
                ),
            )
        self.button(
            text="برگشت",
            callback_data=Servers.Callback(
                server_id=server_id, action=ServersAction.show
            ),
        )
        self.adjust(1, 2, 1, 2, 1, 1)
