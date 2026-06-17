from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.keyboards.base import MainMenu
from app.keyboards.user import proxy, purchase
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.keyboards.user.payment import (
    ChargePanel,
    MinAmountValueError,
    choose_auto_select_method,
)
from app.models.user import User
from app.utils import settings, texts
from app.utils.filters import IsJoinedToChannel

from . import router


@router.callback_query(ChargePanel.DirectCallback.filter())
async def pay_for_service(
    query: CallbackQuery,
    user: User,
    callback_data: ChargePanel.DirectCallback,
):
    _settings = settings.get_settings()
    if callback_data.mode == "purchase":
        back_callback = purchase.Services.Callback(
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            action=purchase.ServicesActions.show_service,
        )
    else:
        back_callback = proxy.RenewSelectMethod.Callback(
            proxy_id=callback_data.proxy_id,
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            user_id=user.id,
            current_page=callback_data.current_page,
            method=proxy.RenewMethods.reserve
            if callback_data.mode == "reserve"
            else proxy.RenewMethods.now,
        )

    try:
        amount = callback_data.amount
        markup = ChargePanel(
            _settings=_settings,
            amount=amount,
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            proxy_id=callback_data.proxy_id,
            direct_mode=callback_data.mode,
            back_callback=back_callback,
            auto_select_plugin=await choose_auto_select_method(_settings=_settings),
        ).as_markup()
    except MinAmountValueError as err:
        amount = err.min_amount
        markup = ChargePanel(
            _settings=_settings,
            amount=amount,
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            direct_mode=callback_data.mode,
            back_callback=back_callback,
            auto_select_plugin=await choose_auto_select_method(_settings=_settings),
        ).as_markup()
    if len(markup.inline_keyboard) > 0:
        text = texts.get_texts().charge.value
        text += f"""
💲مبلغ قابل پرداخت: {amount:,} تومان
"""
        return await query.message.edit_text(text=text, reply_markup=markup)
    return await query.answer(
        "در حال حاضر درگاه پرداخت غیرفعال می‌باشد! برای شارژ حساب با مدیر سیستم تماس بگیرید."
    )


@router.message(F.text == MainMenu.charge, IsJoinedToChannel())
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.charge))
async def charge(qmsg: Message | CallbackQuery, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        text = "🌀 عملیات لغو شد!"
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text)
        else:
            await qmsg.answer(text=text, reply_markup=ReplyKeyboardRemove())
    _settings = settings.get_settings()
    markup = ChargePanel(
        _settings=_settings,
        auto_select_plugin=await choose_auto_select_method(_settings=_settings),
    ).as_markup()
    if len(markup.inline_keyboard) > 0:
        text = texts.get_texts().charge.value
    else:
        markup = None
        text = """
در حال حاضر درگاه پرداخت غیرفعال می‌باشد! برای شارژ حساب با مدیر سیستم تماس بگیرید.
"""
    if isinstance(qmsg, Message):
        return await qmsg.answer(text, reply_markup=markup)
    return await qmsg.message.edit_text(text, reply_markup=markup)
