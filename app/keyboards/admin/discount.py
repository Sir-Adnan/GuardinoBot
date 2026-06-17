from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.service import Discount, Service

from .admin import AdminPanel, AdminPanelAction
from .service import Services, ServicesAction


class DiscountsAction(str, Enum):
    show = "show"
    add = "add"
    save_new = "save_new"


class Discounts(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="discounts"):
        discount_id: int = 0
        action: DiscountsAction
        current_page: int = 0

    def __init__(
        self, discounts: list[Discount], current_page: int = 0, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        for discount in discounts:
            self.button(
                text=f"{f'{discount.code} : ' if discount.code else ''}{discount.id} : {discount.percentage}% : {'✅' if discount.is_active else '❌'}",
                callback_data=self.Callback(
                    discount_id=discount.id,
                    action=DiscountsAction.show,
                    current_page=0,
                ),
            )
        self.button(
            text="افزودن تخفیف",
            callback_data=self.Callback(action=DiscountsAction.add, current_page=0),
        )
        self.button(
            text="برگشت",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.services),
        )
        self.adjust(1, 1)


class DiscountActAction(str, Enum):
    rem = "rem"
    flip_on_purchase = "on_purchase"
    flip_on_renew = "on_renew"
    flip_once_per_user = "once_per_user"
    edit = "edit"
    flip_is_active = "flip_active"


class DiscountAct(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="discaction"):
        discount_id: int
        action: DiscountActAction
        confirmed: bool = False

    def __init__(self, discount: Discount, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text=f"وضعیت: {'✅ فعال' if discount.is_active else '❌ غیرفعال'}",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.flip_is_active
            ),
        )
        self.button(
            text="اعمال روی:",
            callback_data="ph",
        )
        self.button(
            text=f"خرید سرویس: {'✅' if discount.on_purchase else '❌'}",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.flip_on_purchase
            ),
        )
        self.button(
            text=f"تمدید سرویس: {'✅' if discount.on_renew else '❌'}",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.flip_on_renew
            ),
        )
        self.button(
            text=f"هر کاربر فقط یک بار: {'✅' if discount.once_per_user else '❌'}",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.flip_once_per_user
            ),
        )
        self.button(
            text="حذف تخفیف",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.rem
            ),
        )
        self.button(
            text="ویرایش تخفیف",
            callback_data=self.Callback(
                discount_id=discount.id, action=DiscountActAction.edit
            ),
        )
        self.button(
            text="برگشت",
            callback_data=Services.Callback(action=ServicesAction.discounts),
        )
        self.adjust(1, 1, 2, 1)


class SelectServices(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slctsrvsdisc"):
        service_id: int = 0

    def __init__(
        self, services: list[Service], selected_services: list[int], *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        for service in services:
            self.button(
                text=f"{service.display_name} {'✅' if service.id in selected_services else '❌'}",
                callback_data=self.Callback(service_id=service.id),
            )
        self.button(
            text="تایید",
            callback_data=Discounts.Callback(action=DiscountsAction.save_new),
        )
        self.button(
            text="لغو",
            callback_data=Services.Callback(action=ServicesAction.discounts),
        )
        self.adjust(1, 1, 1)


class ConfirmDiscountAction(InlineKeyboardBuilder):
    def __init__(
        self, discount: Discount, action: DiscountActAction, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.button(
            text="تایید",
            callback_data=DiscountAct.Callback(
                discount_id=discount.id, action=action, confirmed=True
            ),
        )
        self.button(
            text="برگشت",
            callback_data=Discounts.Callback(
                discount_id=discount.id, action=DiscountsAction.show
            ),
        )
