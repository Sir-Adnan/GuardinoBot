from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.premium import premium_button
from app.keyboards.user import payment
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.models.service import Service


class ServicesActions(str, Enum):
    show = "show"
    show_service = "show_service"
    purchase = "purchase"


class Services(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="servicss"):
        service_id: int = 0
        menu_id: int = 0
        action: ServicesActions

    def __init__(
        self,
        sub_menues: list[tuple[int, str]],
        services: list[tuple[int, str]],
        menu_id: int = 0,
        parent_menu_id: int = 0,
        has_previous: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        for sm in sub_menues:
            self.button(
                text=sm[1],
                callback_data=self.Callback(
                    menu_id=sm[0],
                    action=ServicesActions.show,
                ),
            )
        for service in services:
            self.button(
                text=service[1],
                callback_data=self.Callback(
                    service_id=service[0],
                    menu_id=menu_id,
                    action=ServicesActions.show_service,
                ),
            )
        if has_previous:
            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=self.Callback(
                        menu_id=parent_menu_id or 0, action=ServicesActions.show
                    ),
                )
            )
        self.adjust(1, 1, 1)


class PurchaseService(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="prchssrv"):
        service_id: int
        menu_id: int = 0
        discount_id: int | None = 0

    def __init__(
        self,
        service_id: int,
        has_balance: bool = True,
        pay_amount: int | None = None,
        discount_id: int | None = None,
        menu_id: int = 0,
        back_callback: CallbackData | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if has_balance:
            self.add(
                premium_button(
                    text="🛒 خرید سرویس",
                    key="purchase_buy",
                    callback_data=self.Callback(
                        service_id=service_id, discount_id=discount_id
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
                        mode="purchase",
                    ),
                )
            )
        if not discount_id:
            self.add(
                premium_button(
                    text="🎁 کد تخفیف دارم",
                    key="purchase_redeem",
                    callback_data=UserPanel.Callback(
                        action=UserPanelAction.redeem_code,
                        service_id=service_id,
                        menu_id=menu_id,
                        mode="purchase",
                    ),
                )
            )
        self.add(
            premium_button(
                text="🔙 برگشت",
                key="common_back",
                callback_data=back_callback,
            )
        )
        self.adjust(1, 1)
