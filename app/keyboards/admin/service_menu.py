from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.service import Service, ServiceMenu

from .admin import AdminPanel, AdminPanelAction


class MenuAction(str, Enum):
    expand = "expand"
    edit_title = "edit_title"
    edit_description = "edit_description"
    toggle_purchase = "toggle_purchase"
    toggle_renew = "toggle_renew"
    toggle_resellers_only = "resellers_only"
    toggle_users_only = "users_only"
    add_sub_menu = "add_sub_menu"
    add_service = "add_service"
    save_new = "save_new"
    delete = "delete"
    service_ph = "service_ph"


class Menues(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="menues"):
        menu_id: int = 0
        action: MenuAction
        confirmed: bool = False

    def __init__(
        self,
        sub_menues: list[ServiceMenu],
        services: list[Service],
        menu: ServiceMenu | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for m in sub_menues:
            self.button(
                text=f"{m.title}",
                callback_data=self.Callback(menu_id=m.id, action=MenuAction.expand),
            )
        for service in services:
            self.button(
                text=f"{service.display_name}",
                callback_data=self.Callback(
                    menu_id=menu.id if menu else 0, action=MenuAction.service_ph
                ),
            )
        if menu:
            self.button(
                text="ویرایش نام",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.edit_title
                ),
            )
            self.button(
                text="ویرایش توضیحات",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.edit_description
                ),
            )
            self.button(
                text=f"فقط فروشنده‌ها {'✅' if menu.resellers_only else '❌'}",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.toggle_resellers_only
                ),
            )
            self.button(
                text=f"فقط کاربران معمولی {'✅' if menu.users_only else '❌'}",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.toggle_users_only
                ),
            )
            self.button(
                text=f"نمایش در لیست خرید {'✅' if menu.purchase else '❌'}",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.toggle_purchase
                ),
            )
            self.button(
                text=f"نمایش در لیست تمدید {'✅' if menu.renew else '❌'}",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.toggle_renew
                ),
            )
            self.button(
                text="ویرایش سرویس‌های این منو",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.add_service
                ),
            )
            self.button(
                text="حذف این زیرمنو",
                callback_data=self.Callback(menu_id=menu.id, action=MenuAction.delete),
            )
            self.button(
                text="افزودن زیرمنو",
                callback_data=self.Callback(
                    menu_id=menu.id, action=MenuAction.add_sub_menu
                ),
            )
            if menu.parent_id is None:
                self.button(
                    text="برگشت",
                    callback_data=AdminPanel.Callback(
                        action=AdminPanelAction.service_menues
                    ),
                )
            else:
                self.button(
                    text="برگشت",
                    callback_data=self.Callback(
                        menu_id=menu.parent_id, action=MenuAction.expand
                    ),
                )
        else:
            self.button(
                text="افزودن زیرمنو",
                callback_data=self.Callback(action=MenuAction.add_sub_menu),
            )
            self.button(
                text="برگشت",
                callback_data=AdminPanel.Callback(action=AdminPanelAction.panel),
            )

        self.adjust(1, 1)


class MenuesConfirm(InlineKeyboardBuilder):
    def __init__(self, menu: ServiceMenu, action: MenuAction, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=Menues.Callback(
                menu_id=menu.id, action=action, confirmed=True
            ),
        )
        self.button(
            text="برگشت",
            callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
        )
        self.adjust(1, 1)


class SelectServiceActions(str, Enum):
    next = "next"
    toggle_selection = "toggle_selection"


class SelectServices(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="mnslctsrvss"):
        service_id: int = 0
        action: SelectServiceActions
        for_edit: bool = False

    def __init__(
        self,
        services: list[Service],
        selected_services: list[int],
        for_edit: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=f"{service.display_name} {'✅' if service.id in selected_services else ''}",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=SelectServiceActions.toggle_selection,
                    for_edit=for_edit,
                ),
            )
        self.button(
            text="تأیید",
            callback_data=self.Callback(
                action=SelectServiceActions.next, for_edit=for_edit
            ),
        )
        self.button(
            text="لغو",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.service_menues),
        )

        self.adjust(1, 1, 1)
