from enum import Enum
from typing import Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.server import Server
from app.models.service import Service
from app.models.user import User

from . import admin

USAGE_RESET_STRATEGY = {
    Service.UsageResetStrategy.no_reset: "غیرفعال",
    Service.UsageResetStrategy.day: "روزانه",
    Service.UsageResetStrategy.week: "هفتگی",
    Service.UsageResetStrategy.month: "ماهانه",
    Service.UsageResetStrategy.year: "سالانه",
}


class ServicesAction(str, Enum):
    show = "show"
    add = "add"
    save_new = "save_new"
    discounts = "discounts"
    sv_priorities = "priorities"


class Services(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="services"):
        service_id: int = 0
        action: ServicesAction

    def __init__(self, services: list[Service], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=f"{service.name}",
                callback_data=self.Callback(
                    service_id=service.id, action=ServicesAction.show
                ),
            )
        self.button(
            text="افزودن سرویس",
            callback_data=self.Callback(action=ServicesAction.add),
        )
        self.button(
            text="مدیریت تخفیف‌ها",
            callback_data=self.Callback(action=ServicesAction.discounts),
        )
        self.button(
            text="ترتیب و اولویت سرویس‌ها",
            callback_data=self.Callback(action=ServicesAction.sv_priorities),
        )
        self.button(
            text="برگشت",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.panel
            ),
        )
        self.adjust(1, 1)


class ServicesPriority(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="pservprios"):
        service_id: int = 0
        direction: int = 1

    def __init__(self, services: list[Service], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text="🔼",
                callback_data=self.Callback(service_id=service.id, direction=-1),
            )
            self.button(text=f"{service.name}", callback_data="_ph")
            self.button(
                text="🔽",
                callback_data=self.Callback(service_id=service.id, direction=1),
            )
        self.button(
            text="برگشت",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.services
            ),
        )
        self.adjust(*[3 for _ in range(len(services))], 1)


class ServiceActAction(str, Enum):
    rem = "rem"
    edit = "edit"
    flip_purchase = "flip_purchase"
    flip_renew = "flip_renew"
    limits = "limits"
    flip_one_time_only = "flip_one_time_only"
    flip_is_test_service = "flip_is_test_service"
    flip_create_on_hold_users = "flip_create_on_hold_users"
    flip_append_available_data_renew = "flip_append_available_data_renew"
    cycle_usage_reset_strategy = "cycle_usage_reset_strategy"
    flip_all_inbounds = "flip_all_inbounds"
    cycle_flow = "cycle_flow"
    broadcast = "broadcast"
    bulk_update = "bulk_update"

    edit_inbounds = "edit_inbounds"
    save_inbounds = "save_inbounds"

    apply_inbounds_to_services = "apl_inbs_srvc"
    apply_inbounds_to_users = "apl_inbs_usr"


class ServiceAct(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="srviceact"):
        service_id: int
        action: ServiceActAction
        confirmed: bool = False

    def __init__(
        self, service: Service, panel_type: str | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        pt = panel_type or "marzban"
        is_marzban = pt == "marzban"
        is_guardino = pt == "guardino"
        is_pasarguard = pt == "pasarguard"

        self.button(
            text="حذف سرویس",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.rem
            ),
        )
        self.button(text="وضعیت نمایش در لیست‌ها:", callback_data="plchldr")
        self.button(
            text=f"لیست خرید: {'✅' if service.purchaseable else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.flip_purchase
            ),
        )
        self.button(
            text=f"لیست تمدید: {'✅' if service.renewable else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.flip_renew
            ),
        )
        self.button(
            text="محدودیت خرید کاربران",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.limits
            ),
        )
        self.button(
            text=f"امکان خرید فقط یک بار: {'✅' if service.one_time_only else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.flip_one_time_only
            ),
        )
        self.button(
            text=f"سرویس تست: {'✅' if service.is_test_service else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.flip_is_test_service
            ),
        )
        # on_hold ("start on first connect") isn't mapped for Guardino.
        if not is_guardino:
            self.button(
                text=f"شروع از اولین اتصال: {'✅' if service.create_on_hold_users else '❌'}",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActAction.flip_create_on_hold_users,
                ),
            )
        self.button(
            text=f"بازنشانی خودکار حجم: {USAGE_RESET_STRATEGY.get(service.usage_reset_strategy)}",
            callback_data=self.Callback(
                service_id=service.id,
                action=ServiceActAction.cycle_usage_reset_strategy,
            ),
        )
        self.button(
            text=f"اضافه شدن حجم باقیمانده به دوره بعد: {'✅' if service.append_available_data_renew else '❌'}",
            callback_data=self.Callback(
                service_id=service.id,
                action=ServiceActAction.flip_append_available_data_renew,
            ),
        )
        # "send all inbounds" + "vless flow" are Marzban-only concepts.
        if is_marzban:
            self.button(
                text=f"ارسال همه اینباند‌ها: {'✅' if service.all_inbounds else '❌'}",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActAction.flip_all_inbounds,
                    confirmed=True,
                ),
            )
        # network edit: inbounds (Marzban) / groups (PasarGuard) / nodes (Guardino).
        edit_net_label = (
            "ویرایش نودها"
            if is_guardino
            else ("ویرایش گروه‌ها" if is_pasarguard else "ویرایش اینباند‌ها")
        )
        self.button(
            text=edit_net_label,
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.edit_inbounds
            ),
        )
        if is_marzban:
            self.button(
                text=f"vless flow: {service.flow.value}",
                callback_data=self.Callback(
                    service_id=service.id, action=ServiceActAction.cycle_flow
                ),
            )
        # re-applying provisioning to existing users is a no-op for Guardino.
        if not is_guardino:
            self.button(
                text="اعمال تنظیمات برای کاربران قبلی",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActAction.apply_inbounds_to_users,
                ),
            )
        self.button(
            text="ویرایش سرویس",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.edit
            ),
        )
        self.button(
            text="پیام همگانی به کاربران این سرویس",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.broadcast
            ),
        )
        self.button(
            text="ویرایش همگانی اشتراک‌ها",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActAction.bulk_update
            ),
        )
        self.button(
            text="برگشت",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.services
            ),
        )
        self.adjust(1)


class ServiceActLimitAction(str, Enum):
    flip_resellers_only = "flip_resellers_only"
    flip_users_only = "flip_users_only"
    flip_user_filter = "filp_user_filter"
    select_users = "select_users"


class ServiceActLimit(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="svactlimi"):
        service_id: int
        action: ServiceActLimitAction

    def __init__(self, service: Service, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"فقط فروشندگان: {'✅' if service.resellers_only else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActLimitAction.flip_resellers_only
            ),
        )
        self.button(
            text=f"فقط کاربران معمولی: {'✅' if service.users_only else '❌'}",
            callback_data=self.Callback(
                service_id=service.id, action=ServiceActLimitAction.flip_users_only
            ),
        )
        self.button(
            text=f"فقط کاربران مشخص شده: {'✅' if service.user_filter else '❌'}",
            callback_data=self.Callback(
                service_id=service.id,
                action=ServiceActLimitAction.flip_user_filter,
            ),
        )
        if service.user_filter:
            self.button(
                text="انتخاب لیست کاربران",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActLimitAction.select_users,
                ),
            )
        self.button(
            text="برگشت",
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
        )
        self.adjust(1, 1, 1)


class ServiceActLimitUsers(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="svactlimi"):
        service_id: int
        action: ServiceActLimitAction
        user_id: int | None = None
        current_page: int = 0

    def __init__(
        self,
        service: Service,
        users: list[User],
        selected_users: list[int],
        current_page: int = 0,
        count: int = 0,
        next_page: bool = False,
        prev_page: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        for user in users:
            self.button(
                text=f"{'✅' if user.id in selected_users else ''} {user.custom_name if user.custom_name else user.name} ({f'@{user.username}' if user.username else user.id})",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActLimitAction.select_users,
                    user_id=user.id,
                    current_page=current_page,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ صفحه قبل",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActLimitAction.select_users,
                    current_page=current_page - 1,
                ),
            )
        if next_page:
            self.button(
                text="➡️ صفحه بعد",
                callback_data=self.Callback(
                    service_id=service.id,
                    action=ServiceActLimitAction.select_users,
                    current_page=current_page + 1,
                ),
            )
        self.button(
            text="برگشت به منوی سرویس",
            callback_data=ServiceAct.Callback(
                service_id=service.id,
                action=ServiceActAction.limits,
            ),
        )
        self.adjust(1, 1, 1)


class ConfirmServiceAction(InlineKeyboardBuilder):
    def __init__(
        self, service: Service, action: ServiceActAction, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.button(
            text="تایید",
            callback_data=ServiceAct.Callback(
                service_id=service.id, action=action, confirmed=True
            ),
        )
        self.button(
            text="برگشت",
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
        )


class SelectServer(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slctsrv"):
        server_id: int

    def __init__(self, servers: list[Server], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for server in servers:
            self.button(
                text=f"{server.name} | {server.host}",
                callback_data=self.Callback(server_id=server.id),
            )
        self.button(
            text="برگشت",
            callback_data=admin.AdminPanel.Callback(
                action=admin.AdminPanelAction.services
            ),
        )
        self.adjust(1, 1)


class SelectServicesBulk(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slctblksrvcc"):
        service_id: int
        server_id: int
        sid: int | None = None
        action: Literal["all", "none"] | None = None

    def __init__(
        self,
        service_id: int,
        server_id: int,
        services: list[Service],
        selected: list[int],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=f"{service.display_name} {'✅' if service.id in selected else ''}",
                callback_data=self.Callback(
                    service_id=service_id, server_id=server_id, sid=service.id
                ),
            )
        self.button(
            text="انتخاب همه",
            callback_data=self.Callback(
                service_id=service_id, server_id=server_id, action="all"
            ),
        )
        self.button(
            text="حذف انتخاب همه",
            callback_data=self.Callback(
                service_id=service_id, server_id=server_id, action="none"
            ),
        )
        self.button(
            text="تأیید",
            callback_data=SelectInbounds.Callback(
                server_id=server_id,
                service_id=service_id,
                for_edit=True,
            ),
        )
        self.adjust(1, 1)


class SelectInbounds(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slctinbnd"):
        server_id: int
        protocol: str | None = None
        inbound: str | None = None
        for_edit: bool = False
        service_id: int | None = None

    def __init__(
        self,
        inbounds: dict[str, list[str]],
        selected_inbounds: dict[str, list[str]],
        server_id: int,
        for_edit: bool = False,
        service_id: int = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for protocol, protocol_inbounds in inbounds.items():
            selected_protocol_inbounds = [
                inbound
                for inbound in protocol_inbounds
                if inbound in selected_inbounds.get(protocol, [])
            ]
            if protocol in selected_inbounds and len(selected_protocol_inbounds) > 0:
                self.button(
                    text=f"✅ {protocol.upper()}",
                    callback_data=self.Callback(
                        server_id=server_id,
                        protocol=protocol,
                        for_edit=for_edit,
                        service_id=service_id,
                    ),
                )
                for inbound in protocol_inbounds:
                    self.button(
                        text=f"{'✅' if inbound in selected_protocol_inbounds else '❌'} {inbound}",
                        callback_data=self.Callback(
                            server_id=server_id,
                            protocol=protocol,
                            inbound=inbound,
                            for_edit=for_edit,
                            service_id=service_id,
                        ),
                    )
            else:
                self.button(
                    text=f"❌ {protocol}",
                    callback_data=self.Callback(
                        server_id=server_id,
                        protocol=protocol,
                        for_edit=for_edit,
                        service_id=service_id,
                    ),
                )

        if for_edit:
            self.button(
                text="اعمال تغییرات به سرویس دیگر",
                callback_data=SelectServicesBulk.Callback(
                    service_id=service_id,
                    server_id=server_id,
                ),
            )
            self.button(
                text="زخیره",
                callback_data=ServiceAct.Callback(
                    service_id=service_id, action=ServiceActAction.save_inbounds
                ),
            )
            self.button(
                text="لغو",
                callback_data=Services.Callback(
                    service_id=service_id, action=ServicesAction.show
                ),
            )
        else:
            self.button(
                text="زخیره",
                callback_data=Services.Callback(
                    server_id=server_id, action=ServicesAction.save_new
                ),
            )
            self.button(
                text="لغو",
                callback_data=admin.AdminPanel.Callback(
                    action=admin.AdminPanelAction.services
                ),
            )
        self.adjust(1, 1, 1)


class SelectGroups(InlineKeyboardBuilder):
    """PasarGuard group selection — parallel to SelectInbounds but toggles
    integer group ids (stored in Service.panel_config.group_ids)."""

    class Callback(CallbackData, prefix="slctgrp"):
        server_id: int
        group_id: int | None = None
        for_edit: bool = False
        service_id: int | None = None

    def __init__(
        self,
        groups: list[dict],
        selected_group_ids: list[int],
        server_id: int,
        for_edit: bool = False,
        service_id: int = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for group in groups:
            gid = group.get("id")
            name = group.get("name") or str(gid)
            self.button(
                text=f"{'✅' if gid in selected_group_ids else '❌'} {name}",
                callback_data=self.Callback(
                    server_id=server_id,
                    group_id=gid,
                    for_edit=for_edit,
                    service_id=service_id,
                ),
            )
        if for_edit:
            self.button(
                text="زخیره",
                callback_data=ServiceAct.Callback(
                    service_id=service_id, action=ServiceActAction.save_inbounds
                ),
            )
            self.button(
                text="لغو",
                callback_data=Services.Callback(
                    service_id=service_id, action=ServicesAction.show
                ),
            )
        else:
            self.button(
                text="زخیره",
                callback_data=Services.Callback(
                    server_id=server_id, action=ServicesAction.save_new
                ),
            )
            self.button(
                text="لغو",
                callback_data=admin.AdminPanel.Callback(
                    action=admin.AdminPanelAction.services
                ),
            )
        self.adjust(1)


class SelectNodes(InlineKeyboardBuilder):
    """Guardino node selection — parallel to SelectGroups; toggles integer node
    ids stored in Service.panel_config.node_ids. Selecting none lets the hub use
    the reseller's default node mode."""

    class Callback(CallbackData, prefix="slctnode"):
        server_id: int
        node_id: int | None = None
        for_edit: bool = False
        service_id: int | None = None

    def __init__(
        self,
        nodes: list[dict],
        selected_node_ids: list[int],
        server_id: int,
        for_edit: bool = False,
        service_id: int = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for node in nodes:
            nid = node.get("id")
            name = node.get("name") or str(nid)
            self.button(
                text=f"{'✅' if nid in selected_node_ids else '❌'} {name}",
                callback_data=self.Callback(
                    server_id=server_id,
                    node_id=nid,
                    for_edit=for_edit,
                    service_id=service_id,
                ),
            )
        if for_edit:
            self.button(
                text="زخیره",
                callback_data=ServiceAct.Callback(
                    service_id=service_id, action=ServiceActAction.save_inbounds
                ),
            )
            self.button(
                text="لغو",
                callback_data=Services.Callback(
                    service_id=service_id, action=ServicesAction.show
                ),
            )
        else:
            self.button(
                text="زخیره",
                callback_data=Services.Callback(
                    server_id=server_id, action=ServicesAction.save_new
                ),
            )
            self.button(
                text="لغو",
                callback_data=admin.AdminPanel.Callback(
                    action=admin.AdminPanelAction.services
                ),
            )
        self.adjust(1)


class EditServiceAction(str, Enum):
    data_limit = "edit_data_lmit"
    expire_duration = "edit_expire_duration"
    price = "edit_price"
    name = "edit_name"
    save = "save"


class EditService(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="editsrvic"):
        service_id: int
        action: EditServiceAction

    def __init__(self, service: Service, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for action in EditServiceAction:
            if not action.value.startswith("edit_"):
                continue
            self.button(
                text=f"ویرایش {action.name.capitalize()}",
                callback_data=self.Callback(service_id=service.id, action=action),
            )
        self.button(
            text="ذخیره",
            callback_data=self.Callback(
                service_id=service.id, action=EditServiceAction.save
            ),
        )
        self.button(
            text="لغو",
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
        )
        self.adjust(1, 1, 2, 1, 1)
