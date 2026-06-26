from enum import Enum
from typing import TYPE_CHECKING

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.admin import user
from app.keyboards.premium import premium_button
from app.keyboards.user import account, payment
from app.models.proxy import Proxy, ProxyStatus
from app.models.user import UserSetting
from app.utils.buttons import sanitize_style

if TYPE_CHECKING:
    from app.utils import settings

PROXY_STATUS = {
    ProxyStatus.active: "✅",
    ProxyStatus.disabled: "❌",
    ProxyStatus.limited: "🔒",
    ProxyStatus.expired: "⏳",
    ProxyStatus.on_hold: "⏸",
}

SORT_PROXY = {
    UserSetting.SortProxyList.created_ascending: "تاریخ ساخت - قدیمی ترین",
    UserSetting.SortProxyList.created_descending: "تاریخ ساخت - جدید ترین",
    UserSetting.SortProxyList.renewed_ascending: "تاریخ تمدید - قدیمی ترین",
    UserSetting.SortProxyList.renewed_descending: "تاریخ تمدید - جدید ترین",
}


FILTER_PROXY = {
    UserSetting.FilterProxyList.all: "همه",
    UserSetting.FilterProxyList.active: "فعال",
    UserSetting.FilterProxyList.disabled: "غیرفعال",
    UserSetting.FilterProxyList.limited: "محدود شده",
    UserSetting.FilterProxyList.expired: "منقضی شده",
}


class ProxiesActions(str, Enum):
    show = "show"
    show_proxy = "show_proxy"
    cycle_sort = "cycle_sort"
    cycle_filter = "cycle_filter"
    search = "search"
    refresh = "refresh"


class Proxies(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prxss"):
        proxy_id: int = 0
        user_id: int | None = None
        parent_id: int | None = None
        action: ProxiesActions
        current_page: int = 0
        search_text: str | None = None

    def __init__(
        self,
        proxies: list[Proxy],
        count: int,
        user_id: int | None = None,
        parent_id: int | None = None,
        current_page: int = 0,
        sort_by: UserSetting.SortProxyList = UserSetting.SortProxyList.created_descending,
        filter_by: UserSetting.FilterProxyList = UserSetting.FilterProxyList.all,
        next_page: bool = False,
        prev_page: bool = False,
        search_text: str = None,
        back_to_user_info: bool = False,
        *args,
        **kwargs,
    ) -> None:
        """proxies should have 'proxy.server' prefetched"""
        super().__init__(*args, **kwargs)
        if current_page == 0:
            if count > 10 or sort_by != UserSetting.SortProxyList.created_descending:
                self.button(
                    text=f"📈 مرتب سازی: {SORT_PROXY.get(sort_by)}",
                    callback_data=self.Callback(
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxiesActions.cycle_sort,
                        search_text=search_text,
                    ),
                )
            if count > 10 or filter_by != UserSetting.FilterProxyList.all:
                self.button(
                    text=f"📈 نمایش: {FILTER_PROXY.get(filter_by)}",
                    callback_data=self.Callback(
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxiesActions.cycle_filter,
                        search_text=search_text,
                    ),
                )
            if count > 10:
                self.button(
                    text="♻️ به روز رسانی وضعیت اشتراک‌ها",
                    callback_data=self.Callback(
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxiesActions.refresh,
                        search_text=search_text,
                    ),
                )
                if search_text:
                    self.button(
                        text=f"🔍 جستجو: {search_text}",
                        callback_data=self.Callback(
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxiesActions.search,
                            search_text=search_text,
                        ),
                    )
                else:
                    self.button(
                        text="🔍 جستجو",
                        callback_data=self.Callback(
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxiesActions.search,
                            search_text=search_text,
                        ),
                    )
        elif search_text:
            self.button(
                text=f"🔍 جستجو: {search_text}",
                callback_data=self.Callback(
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxiesActions.search,
                    search_text=search_text,
                ),
            )
        for proxy in proxies:
            self.button(
                text=f"{PROXY_STATUS.get(proxy.status)} {proxy.username} ({proxy.custom_name or proxy.service.display_name if proxy.service_id else ''})",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxiesActions.show_proxy,
                    search_text=search_text,
                ),
            )
        if prev_page:
            self.button(
                text="⬅️ صفحه قبل",
                callback_data=self.Callback(
                    user_id=user_id,
                    parent_id=parent_id,
                    action=ProxiesActions.show,
                    current_page=current_page - 1,
                    search_text=search_text,
                ),
            )
        if next_page:
            self.button(
                text="➡️ صفحه بعد",
                callback_data=self.Callback(
                    user_id=user_id,
                    parent_id=parent_id,
                    action=ProxiesActions.show,
                    current_page=current_page + 1,
                    search_text=search_text,
                ),
            )
        if parent_id:
            self.button(
                text="🔙 برگشت",
                callback_data=account.ManageUsers.Callback(
                    user_id=user_id,
                    action=account.ManageUsersAction.show_user,
                    current_page=0,
                ),
            )
        if current_page == 0 and search_text is not None:
            self.button(
                text="♻️ نمایش همه اشتراک‌ها",
                callback_data=self.Callback(
                    user_id=user_id,
                    parent_id=parent_id,
                    action=ProxiesActions.show,
                    current_page=current_page,
                ),
            )
        if current_page == 0 and count > 10:
            orders = [1 for _ in range(14)]
        else:
            orders = [1 for _ in range(11)]
        orders.extend([2, 1])
        if back_to_user_info:
            orders.append(1)
            self.button(
                text="🔙 برگشت به تنظیمات کاربر",
                callback_data=user.ManageUser.Callback(
                    user_id=user_id,
                    action=user.ManageUserAction.info,
                ),
            )
        self.adjust(*orders)


class ProxyPanelActions(str, Enum):
    links = "links"
    reset_password = "reset_password"
    reset_uuid = "reset_uuid"
    reset_subscription = "reset_subscription"
    renew = "renew"
    set_name = "set_name"
    remove = "remove"
    links_allqr = "allqr"
    links_subqr = "subqr"
    show_reserve = "show_reserve"
    delete_wpayback = "delete_wpayback"

    disable = "disable"
    enable = "enable"


class ProxyPanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prxpnl"):
        proxy_id: int
        user_id: int | None = None
        current_page: int = 0
        action: ProxyPanelActions
        confirmed: bool = False

    def __init__(
        self,
        proxy: Proxy,
        _settings: "settings.Settings",
        user_id: int | None = None,
        current_page: int = 0,
        show_reserve: bool = False,
        can_delete: bool = False,
        renewable: bool = True,
        can_disable: bool = False,
        can_enable: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if proxy.status in [ProxyStatus.active, ProxyStatus.on_hold]:
            if _settings.show_connect_links_button:
                self.add(
                    premium_button(
                        text="🔗 دریافت لینک‌های اتصال",
                        key="proxy_links",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxyPanelActions.links,
                        ),
                    )
                )
            else:
                self.add(
                    premium_button(
                        text="📱 Qr Code اتصال هوشمند",
                        key="links_subqr",
                        callback_data=ProxyPanel.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxyPanelActions.links_subqr,
                        ),
                    )
                )
            if _settings.reset_password_button:
                self.add(
                    premium_button(
                        text="🔑 تغییر پسوورد",
                        key="proxy_reset_password",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxyPanelActions.reset_password,
                        ),
                    )
                )
            if can_disable:
                self.add(
                    premium_button(
                        text="🚫 غیرفعال سازی موقت",
                        key="proxy_disable",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxyPanelActions.disable,
                        ),
                    )
                )
        else:
            if can_enable:
                self.add(
                    premium_button(
                        text="✅ فعال سازی",
                        key="proxy_enable",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ProxyPanelActions.enable,
                        ),
                    )
                )
            self.add(
                premium_button(
                    text="🗑 حذف از لیست اشتراک‌های من",
                    key="proxy_remove",
                    callback_data=self.Callback(
                        proxy_id=proxy.id,
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxyPanelActions.remove,
                    ),
                )
            )
        if renewable:
            self.add(
                premium_button(
                    text="♻️ تمدید سرویس",
                    key="proxy_renew",
                    callback_data=self.Callback(
                        proxy_id=proxy.id,
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxyPanelActions.renew,
                    ),
                )
            )
        self.add(
            premium_button(
                text="✏️ تنظیم اسم دلخواه",
                key="proxy_set_name",
                callback_data=self.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.set_name,
                ),
            )
        )
        if show_reserve:
            self.add(
                premium_button(
                    text="📁 پلن پشتیبان (تمدید خودکار)",
                    key="show_reserve",
                    callback_data=self.Callback(
                        proxy_id=proxy.id,
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxyPanelActions.show_reserve,
                    ),
                )
            )
        if can_delete and (
            proxy.status
            not in [
                ProxyStatus.expired,
                ProxyStatus.limited,
            ]
        ):
            self.add(
                premium_button(
                    text="🗑 حذف و بازگشت وجه",
                    key="proxy_delete_payback",
                    callback_data=self.Callback(
                        proxy_id=proxy.id,
                        user_id=user_id,
                        current_page=current_page,
                        action=ProxyPanelActions.delete_wpayback,
                    ),
                )
            )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=Proxies.Callback(
                    user_id=user_id,
                    action=ProxiesActions.show,
                    current_page=current_page,
                ),
            )
        )
        if proxy.status == ProxyStatus.active:
            if _settings.reset_password_button:
                self.adjust(1, 2, 1, 1)
            else:
                self.adjust(1, 1, 1, 1)
        else:
            self.adjust(1, 1, 1)


class ResetPassword(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy_id: int,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="🔑 تغییر پسوورد",
                key="reset_uuid",
                callback_data=ProxyPanel.Callback(
                    proxy_id=proxy_id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.reset_uuid,
                ),
            )
        )
        self.add(
            premium_button(
                text="🔑 تغییر اتصال هوشمند",
                key="reset_subscription",
                callback_data=ProxyPanel.Callback(
                    proxy_id=proxy_id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.reset_subscription,
                ),
            )
        )
        self.add(
            premium_button(
                text="🔙 لغو",
                key="common_cancel",
                callback_data=Proxies.Callback(
                    proxy_id=proxy_id,
                    user_id=user_id,
                    action=ProxiesActions.show_proxy,
                    current_page=current_page,
                ),
            )
        )
        self.adjust(1, 1)


class ConfirmProxyPanel(InlineKeyboardBuilder):
    def __init__(
        self,
        action: ProxyPanelActions,
        proxy_id: int,
        user_id: int = None,
        current_page: int = 0,
    ) -> None:
        super().__init__()
        self.add(
            premium_button(
                text="⚠️ تأیید",
                key="confirm_action",
                callback_data=ProxyPanel.Callback(
                    proxy_id=proxy_id,
                    user_id=user_id,
                    current_page=current_page,
                    action=action,
                    confirmed=True,
                ),
            )
        )

        self.add(
            premium_button(
                text="🔙 لغو",
                key="common_cancel",
                callback_data=Proxies.Callback(
                    proxy_id=proxy_id,
                    user_id=user_id,
                    action=ProxiesActions.show_proxy,
                    current_page=current_page,
                ),
            )
        )
        self.adjust(1, 1)


class ProxyLinks(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy: Proxy,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="📱 Qr Code",
                key="links_qr",
                callback_data=ProxyPanel.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.links_allqr,
                ),
            )
        )
        self.add(
            premium_button(
                text="📱 Qr Code اتصال هوشمند",
                key="links_subqr",
                callback_data=ProxyPanel.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    current_page=current_page,
                    action=ProxyPanelActions.links_subqr,
                ),
            )
        )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=Proxies.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    action=ProxiesActions.show_proxy,
                    current_page=current_page,
                ),
            )
        )
        self.adjust(1, 1, 1)


class RenewActions(str, Enum):
    show = "show"
    show_service = "show_service"


class RenewSelectService(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="rnwsrvs"):
        proxy_id: int
        service_id: int = 0
        menu_id: int = 0
        user_id: int | None = None
        current_page: int = 0
        action: RenewActions = RenewActions.show

    def __init__(
        self,
        proxy_id: int,
        sub_menues: list[tuple[int, str]],
        services: list[tuple[int, str]],
        menu_id: int = 0,
        parent_menu_id: int = 0,
        has_previous: bool = False,
        current_page: int = 0,
        user_id: int | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for sm in sub_menues:
            self.button(
                text=sm[1],
                callback_data=self.Callback(
                    proxy_id=proxy_id,
                    menu_id=sm[0],
                    user_id=user_id,
                    current_page=current_page,
                    action=RenewActions.show,
                ),
            )
        for service in services:
            self.add(
                premium_button(
                    text=service[1],
                    icon_custom_emoji_id=service[2] if len(service) > 2 else None,
                    style=sanitize_style(service[3]) if len(service) > 3 else None,
                    callback_data=self.Callback(
                        proxy_id=proxy_id,
                        service_id=service[0],
                        menu_id=menu_id,
                        user_id=user_id,
                        current_page=current_page,
                        action=RenewActions.show_service,
                    ),
                )
            )
        if has_previous:
            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=self.Callback(
                        proxy_id=proxy_id,
                        menu_id=parent_menu_id or 0,
                        user_id=user_id,
                        current_page=current_page,
                        action=RenewActions.show,
                    ),
                )
            )
        else:
            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=Proxies.Callback(
                        proxy_id=proxy_id,
                        user_id=user_id,
                        action=ProxiesActions.show_proxy,
                        current_page=current_page,
                    ),
                )
            )
        self.adjust(1, 1, 1, 1)


class RenewMethods(str, Enum):
    now = "now"
    reserve = "reserve"


class RenewSelectMethod(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="rnwmethod"):
        proxy_id: int
        service_id: int
        menu_id: int = 0
        user_id: int | None = None
        discount_id: int | None = None
        current_page: int = 0
        method: RenewMethods
        confirmed: bool = False

    def __init__(
        self,
        proxy_id: int,
        service_id: int,
        menu_id: int | None = None,
        user_id: int | None = None,
        current_page: int = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="♻️ تمدید آنی اشتراک",
                key="renew_now",
                callback_data=self.Callback(
                    proxy_id=proxy_id,
                    service_id=service_id,
                    menu_id=menu_id or 0,
                    user_id=user_id,
                    current_page=current_page,
                    method=RenewMethods.now,
                ),
            )
        )
        self.add(
            premium_button(
                text="🌀 پلن پشتیبان (تمدید خودکار)",
                key="renew_reserve",
                callback_data=self.Callback(
                    proxy_id=proxy_id,
                    service_id=service_id,
                    menu_id=menu_id or 0,
                    user_id=user_id,
                    current_page=current_page,
                    method=RenewMethods.reserve,
                ),
            )
        )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=RenewSelectService.Callback(
                    proxy_id=proxy_id,
                    menu_id=menu_id,
                    user_id=user_id,
                    current_page=current_page,
                    action=RenewActions.show,
                ),
            )
        )
        self.adjust(1, 1, 1)


class ConfirmRenew(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy_id: int,
        service_id: int,
        method: RenewMethods,
        menu_id: int | None = None,
        user_id: int | None = None,
        discount_id: int | None = None,
        current_page: int = 0,
        has_balance: bool = True,
        pay_amount: int | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if has_balance:
            self.add(
                premium_button(
                    text="✅ فعالسازی",
                    key="renew_confirm",
                    callback_data=RenewSelectMethod.Callback(
                        proxy_id=proxy_id,
                        service_id=service_id,
                        menu_id=menu_id or 0,
                        user_id=user_id,
                        discount_id=discount_id,
                        current_page=current_page,
                        method=method,
                        confirmed=True,
                    ),
                )
            )
        else:
            self.add(
                premium_button(
                    text=f"💳 پرداخت {pay_amount:,} تومان",
                    key="purchase_pay",
                    callback_data=payment.ChargePanel.DirectCallback(
                        amount=pay_amount,
                        service_id=service_id,
                        menu_id=menu_id,
                        proxy_id=proxy_id,
                        mode="renew" if method == RenewMethods.now else "reserve",
                    ),
                )
            )
        if not discount_id:
            self.add(
                premium_button(
                    text="🎁 کد تخفیف دارم",
                    key="purchase_redeem",
                    callback_data=account.UserPanel.Callback(
                        action=account.UserPanelAction.redeem_code,
                        service_id=service_id,
                        menu_id=menu_id,
                        proxy_id=proxy_id,
                        user_id=user_id,
                        current_page=current_page,
                        mode="renew" if method == RenewMethods.now else "reserve",
                    ),
                )
            )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=RenewSelectService.Callback(
                    proxy_id=proxy_id,
                    service_id=service_id,
                    menu_id=menu_id,
                    user_id=user_id,
                    current_page=current_page,
                    action=RenewActions.show_service,
                ),
            )
        )
        self.adjust(1, 1)


class ReservePanelAction(str, Enum):
    activate = "activate"
    cancel = "cancel"


class ReservePanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="rsrvpnl"):
        action: ReservePanelAction
        proxy_id: int
        user_id: int | None = None
        current_page: int = 0
        confirmed: bool = False

    def __init__(
        self,
        proxy: Proxy,
        user_id: int | None = None,
        current_page: int = 0,
        cancelable: bool = False,
        action: ReservePanelAction = ReservePanelAction.activate,
        confirmed: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not confirmed:
            self.add(
                premium_button(
                    text="✅ فعالسازی",
                    key="reserve_activate",
                    callback_data=self.Callback(
                        proxy_id=proxy.id,
                        user_id=user_id,
                        current_page=current_page,
                        action=ReservePanelAction.activate,
                        confirmed=confirmed,
                    ),
                )
            )
            if cancelable:
                self.add(
                    premium_button(
                        text="⚠️ لغو پلن پشتیبان",
                        key="reserve_cancel",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ReservePanelAction.cancel,
                            confirmed=confirmed,
                        ),
                    )
                )
        else:
            if action == ReservePanelAction.activate:
                self.add(
                    premium_button(
                        text="✅ فعالسازی",
                        key="reserve_activate",
                        callback_data=self.Callback(
                            proxy_id=proxy.id,
                            user_id=user_id,
                            current_page=current_page,
                            action=ReservePanelAction.activate,
                            confirmed=confirmed,
                        ),
                    )
                )
            elif action == ReservePanelAction.cancel:
                if cancelable:
                    self.add(
                        premium_button(
                            text="⚠️ لغو پلن پشتیبان",
                            key="reserve_cancel",
                            callback_data=self.Callback(
                                proxy_id=proxy.id,
                                user_id=user_id,
                                current_page=current_page,
                                action=ReservePanelAction.cancel,
                                confirmed=confirmed,
                            ),
                        )
                    )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=Proxies.Callback(
                    proxy_id=proxy.id,
                    user_id=user_id,
                    action=ProxiesActions.show_proxy,
                    current_page=current_page,
                ),
            )
        )
        self.adjust(1, 1, 1)


class ProxySettings(InlineKeyboardBuilder):
    def __init__(
        self,
        proxy: Proxy,
        user_id: int | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="⚙️ تنظیمات پروکسی",
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
            ),
        )


def alert_renew_keyboard(proxy_id: int):
    """Single inline 'renew' button for proxy-alert messages → opens the standard
    renew flow for that proxy (the existing ProxyPanel renew callback). Supports
    an optional premium-emoji icon + colour (see app.keyboards.premium)."""
    kb = InlineKeyboardBuilder()
    kb.add(
        premium_button(
            text="🔄 تمدید سرویس",
            key="alert_renew",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy_id, action=ProxyPanelActions.renew
            ),
        )
    )
    return kb.as_markup()


def alert_links_keyboard(proxy_id: int):
    """Inline 'connection links' button for the 'unused subscription' alert →
    opens the proxy's links so the user can finally connect."""
    kb = InlineKeyboardBuilder()
    kb.add(
        premium_button(
            text="🔗 دریافت لینک اتصال",
            key="alert_links",
            callback_data=ProxyPanel.Callback(
                proxy_id=proxy_id, action=ProxyPanelActions.links
            ),
        )
    )
    return kb.as_markup()
