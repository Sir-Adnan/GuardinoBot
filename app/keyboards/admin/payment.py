from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.user import Transaction

from .admin import AdminPanel, AdminPanelAction
from .user import ManageTrx, ManageTrxAction


class AdminPayment(InlineKeyboardBuilder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="Back",
            callback_data=AdminPanel.Callback(action=AdminPanelAction.panel),
        )
        self.adjust(1, 1)


class TrxActActions(str, Enum):
    accept = "accept"
    reject = "reject"


class TrxAct(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="admtrxactacto"):
        user_id: int
        trx_id: int
        action: TrxActActions
        current_page: int = 0
        confirmed: bool = False

    def __init__(
        self, transaction: Transaction, user_id: int, current_page: int, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        if transaction.status == Transaction.Status.finished:
            self.button(
                text="عدم تأیید تراکنش",
                callback_data=self.Callback(
                    user_id=user_id,
                    trx_id=transaction.id,
                    action=TrxActActions.reject,
                    current_page=current_page,
                ),
            )
        else:
            self.button(
                text="تأیید تراکنش",
                callback_data=self.Callback(
                    user_id=user_id,
                    trx_id=transaction.id,
                    action=TrxActActions.accept,
                    current_page=current_page,
                ),
            )
        self.button(
            text="برگشت",
            callback_data=ManageTrx.Callback(
                user_id=user_id,
                action=ManageTrxAction.show_all,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1, 1)


class ConfirmTrxAct(InlineKeyboardBuilder):
    def __init__(
        self,
        transaction: Transaction,
        user_id: int,
        current_page: int,
        action: TrxActActions,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="تایید",
            callback_data=TrxAct.Callback(
                user_id=user_id,
                trx_id=transaction.id,
                action=action,
                current_page=current_page,
                confirmed=True,
            ),
        )
        self.button(
            text="لغو",
            callback_data=ManageTrx.Callback(
                user_id=user_id,
                trx_id=transaction.id,
                action=ManageTrxAction.show,
                current_page=current_page,
            ),
        )
        self.adjust(1, 1, 1)
