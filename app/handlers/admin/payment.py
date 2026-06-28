import json
import sys
from html import escape

from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.keyboards.admin.admin import AdminPanel, AdminPanelAction
from app.keyboards.admin.payment import (
    AdminPayment,
    ConfirmTrxAct,
    TrxAct,
    TrxActActions,
)
from app.keyboards.admin.user import ManageTrx, ManageTrxAction
from app.main import bot, get_bot_username
from app.models.user import CryptoPayment, Transaction, User
from app.plugins.payment.crypto.clients import NowPaymentsError
from app.plugins.payment.crypto.nowpayments_service import check_nowpayments_transaction
from app.plugins.payment.crypto.plisio import PlisioAPI, PlisioError
from app.plugins.payment.crypto.plisio_service import finalize_plisio_payment
from app.utils.filters import AdminAccess, IsSuperUser
from app.utils.settings import get_settings

from . import generate_commands_help, router


@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.payments), IsSuperUser()
)
async def show_payments(query: CallbackQuery, user: User):
    text = """
Payment info: <code>/payment [trx id or amount in format of am_22222]</code> (only works with card to card payments for now)

user commands: /paycmd
"""
    return await query.message.edit_text(text, reply_markup=AdminPayment().as_markup())


async def show_transaction(
    qmsg: Message | CallbackQuery,
    transaction_id: int,
    callback_data: ManageTrx.Callback = None,
):
    transaction = await Transaction.filter(id=transaction_id).first()
    if not transaction:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer("تراکنش یافت نشد!", show_alert=True)
        return await qmsg.reply("تراکنش یافت نشد!")

    text = f"""
شماره تراکنش: <code>{transaction.id}</code>
نوع پرداخت: <code>{transaction.type.name}</code>
وضعیت: <code>{transaction.status.name}</code>

مبلغ: <code>{transaction.amount - transaction.amount_free_given:,}</code>
مبلغ هدیه: <code>{transaction.amount_free_given:,}</code>
مبلغ پرداخت شده: <code>{transaction.amount_paid}</code>

تاریخ اتمام: <code>{transaction.finished_at}</code>

برای دریافت اطلاعات پرداخت کننده روی لینک زیر کلیک کنید:
https://t.me/{get_bot_username()}?start=info_{transaction.user_id}

"""
    if transaction.type == Transaction.PaymentType.crypto:
        await transaction.fetch_related("crypto_payment")
        if transaction.crypto_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.crypto_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.perfectmoney:
        await transaction.fetch_related("perfectmoney_payment")
        if transaction.perfectmoney_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.perfectmoney_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.card_to_card:
        await transaction.fetch_related("card_to_card_payment")
        if transaction.card_to_card_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.card_to_card_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.rial_gateway:
        await transaction.fetch_related("rialgateway_payment")
        if transaction.rialgateway_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.rialgateway_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.by_admin:
        await transaction.fetch_related("byadmin_payment")
        if transaction.byadmin_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.byadmin_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.gift:
        await transaction.fetch_related("gift_payment")
        if transaction.gift_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.gift_payment), indent=2, default=str))}</code>"
    elif transaction.type == Transaction.PaymentType.tronseller:
        await transaction.fetch_related("tronseller_payment")
        if transaction.tronseller_payment:
            text += f"Payment Data:<code>{escape(json.dumps(dict(transaction.tronseller_payment), indent=2, default=str))}</code>"

    if callback_data:
        user_id = callback_data.user_id
        current_page = callback_data.current_page
    else:
        user_id = qmsg.from_user.id
        current_page = 0
    reply_markup = TrxAct(
        transaction=transaction,
        user_id=user_id,
        current_page=current_page,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text=text,
            reply_markup=reply_markup,
        )
    return await qmsg.reply(
        text=text,
        reply_markup=reply_markup,
    )


@router.callback_query(ManageTrx.Callback.filter(F.action == ManageTrxAction.show_all))
@router.message(Command("trx"), IsSuperUser())
async def get_user_transactions_command(
    qmsg: Message | CallbackQuery, user: User, callback_data: ManageTrx.Callback = None
):
    """Get transactions of a user

    Args:
        user (int | str): user id or username of the user

    Example:
        <code>/trx @username</code>
        <code>/trx 123456789</code>
    """
    if callback_data:
        user_id = callback_data.user_id
        current_page = callback_data.current_page
        user_to_get = await User.filter(id=user_id).prefetch_related("setting").first()
    else:
        try:
            _, user_id = qmsg.text.split()
        except ValueError:
            return await qmsg.answer(
                "Could not parse the command! format: /info [user_id|username]"
            )
        if user_id.isnumeric():
            user_to_get = (
                await User.filter(id=int(user_id)).prefetch_related("setting").first()
            )
        else:
            user_to_get = (
                await User.filter(username__iexact=user_id.lstrip("@"))
                .prefetch_related("setting")
                .first()
            )
        current_page = 0

    if not user_to_get:
        return await qmsg.answer(f"User {user_id} not found!")

    q = Transaction.filter(user_id=user_to_get.id)
    total = await q.count()
    if total < 1:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(
                "No payments Found for this user!",
                show_alert=True,
            )
        return await qmsg.reply("No payments Found for this user!")
    q = q.limit(11).offset(0 if current_page == 0 else current_page * 10)
    count = await q.count()
    transactions = await q.order_by("-created_at").all()
    reply_markup = ManageTrx(
        user_id=user_to_get.id,
        transactions=transactions[:10],
        count=count,
        current_page=current_page,
        next_page=True if count > 10 else False,
        prev_page=True if current_page > 0 else False,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            f"User payments ({total})",
            reply_markup=reply_markup,
        )
    return await qmsg.reply(
        f"User payments ({total})",
        reply_markup=reply_markup,
    )


@router.callback_query(ManageTrx.Callback.filter(F.trx_id != 0), IsSuperUser())
@router.message(Command("payment"), AdminAccess())
async def admin_get_payment_command(
    qmsg: Message | CallbackQuery,
    user: User,
    command: CommandObject = None,
    callback_data: ManageTrx.Callback = None,
):
    """Get Payment info

    /payment [Args]

    Args:
        id (int | str): payment id

    Returns:
        Message: payment if found

    Example:
        /payment 444
    """
    if command:
        try:
            transaction_id = int(command.args)
        except ValueError:
            return await qmsg.reply(
                "Could not parse command! format: <code>/payment [trx id]</code>"
            )
        return await show_transaction(qmsg, transaction_id)
    elif callback_data:
        return await show_transaction(qmsg, callback_data.trx_id, callback_data)


@router.callback_query(
    TrxAct.Callback.filter(F.action == TrxActActions.reject), IsSuperUser()
)
async def admin_reject_trx(
    query: CallbackQuery, user: User, callback_data: TrxAct.Callback
):
    transaction = await Transaction.filter(id=callback_data.trx_id).first()
    if not transaction:
        return await query.answer("Transaction not found!", show_alert=True)

    if transaction.status == Transaction.Status.rejected:
        return await query.answer("این تراکنش قبلاً رد شده است!", show_alert=True)

    if not callback_data.confirmed:
        return await query.message.edit_text(
            text="مطمئن هستید که میخواهید این تراکنش عدم تأیید شود؟ مبلغ آن از حساب کاربر کم می‌شود و در صورت وجود اشتراکِ فعال‌شده با این پرداخت، آن اشتراک حذف و فاکتورش باطل می‌گردد!",
            reply_markup=ConfirmTrxAct(
                transaction,
                callback_data.user_id,
                callback_data.current_page,
                callback_data.action,
            ).as_markup(),
        )
    # Undo any activation tied to this transaction (remove the subscription +
    # void its invoice) and set it to rejected — so the balance can't go
    # negative and the customer can't keep a free subscription. Local import
    # avoids a module-load import cycle (jobs imports app.handlers.user.*).
    from app.plugins.payment.jobs import revoke_activated_transaction

    await revoke_activated_transaction(transaction)
    await query.answer("Transaction status changed to rejected!", show_alert=True)
    return await admin_get_payment_command(
        query,
        user,
        callback_data=ManageTrx.Callback(
            user_id=callback_data.user_id,
            trx_id=callback_data.trx_id,
            action=ManageTrxAction.show,
            current_page=callback_data.current_page,
        ),
    )


@router.callback_query(
    TrxAct.Callback.filter(F.action == TrxActActions.accept), IsSuperUser()
)
async def admin_accept_trx(
    query: CallbackQuery, user: User, callback_data: TrxAct.Callback
):
    transaction = await Transaction.filter(id=callback_data.trx_id).first()
    if not transaction:
        return await query.answer("Transaction not found!", show_alert=True)

    if transaction.status == Transaction.Status.finished:
        return await query.answer("Transaction already accepted!", show_alert=True)

    settings = get_settings()

    if transaction.type == Transaction.PaymentType.crypto:
        await transaction.fetch_related("crypto_payment")
        if transaction.crypto_payment.provider == CryptoPayment.Provider.plisio:
            txn_id = (
                transaction.crypto_payment.payment_id
                or transaction.crypto_payment.invoice_id
            )
            if not txn_id:
                return await query.answer("no Plisio txn_id is present!", show_alert=True)
            try:
                ps = settings.payment_plisio
                operation = await PlisioAPI.get_operation(
                    txn_id, api_key=ps.api_key, api_base=ps.api_base
                )
                result = await finalize_plisio_payment(
                    transaction, operation, source="admin_check"
                )
                await query.answer(
                    f"Plisio status: {result.get('status') or 'unknown'}",
                    show_alert=True,
                )
                return await admin_get_payment_command(
                    query,
                    user,
                    callback_data=ManageTrx.Callback(
                        user_id=callback_data.user_id,
                        trx_id=callback_data.trx_id,
                        action=ManageTrxAction.show,
                        current_page=callback_data.current_page,
                    ),
                )
            except PlisioError as exc:
                await query.answer(f"Error: {exc}", show_alert=True)
                raise exc
        try:
            result = await check_nowpayments_transaction(
                transaction, source="admin_check"
            )
            await query.answer(
                f"NowPayments status: {result.get('status') or result.get('result') or 'unknown'}",
                show_alert=True,
            )
            return await admin_get_payment_command(
                query,
                user,
                callback_data=ManageTrx.Callback(
                    user_id=callback_data.user_id,
                    trx_id=callback_data.trx_id,
                    action=ManageTrxAction.show,
                    current_page=callback_data.current_page,
                ),
            )
        except NowPaymentsError as exc:
            await query.answer(f"Error: {exc}")
            raise exc

    elif transaction.type == Transaction.PaymentType.perfectmoney:
        transaction.status = Transaction.Status.finished
        await transaction.save()
        await query.answer("Transaction Accepted!", show_alert=True)
        return await admin_get_payment_command(
            query,
            user,
            callback_data=ManageTrx.Callback(
                user_id=callback_data.user_id,
                trx_id=callback_data.trx_id,
                action=ManageTrxAction.show,
                current_page=callback_data.current_page,
            ),
        )

    elif transaction.type == Transaction.PaymentType.card_to_card:
        await transaction.fetch_related("card_to_card_payment")
        if transaction.card_to_card_payment:
            transaction.status = Transaction.Status.finished
            await transaction.save()
            await query.answer("Transaction Accepted!", show_alert=True)
            text = f"""
✅ پرداخت شما از طریق کارت به کارت با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount - transaction.amount_free_given:,}</b> تومان
‌‌
"""
            await bot.send_message(transaction.user_id, text=text)
            return await admin_get_payment_command(
                query,
                user,
                callback_data=ManageTrx.Callback(
                    user_id=callback_data.user_id,
                    trx_id=callback_data.trx_id,
                    action=ManageTrxAction.show,
                    current_page=callback_data.current_page,
                ),
            )
    elif transaction.type == Transaction.PaymentType.rial_gateway:
        pass
    elif transaction.type == Transaction.PaymentType.by_admin:
        transaction.status = Transaction.Status.finished
        await transaction.save()
        await query.answer("Transaction Accepted!", show_alert=True)
        return await admin_get_payment_command(
            query,
            user,
            callback_data=ManageTrx.Callback(
                user_id=callback_data.user_id,
                trx_id=callback_data.trx_id,
                action=ManageTrxAction.show,
                current_page=callback_data.current_page,
            ),
        )
    elif transaction.type == Transaction.PaymentType.gift:
        transaction.status = Transaction.Status.finished
        await transaction.save()
        await query.answer("Transaction Accepted!", show_alert=True)
        return await admin_get_payment_command(
            query,
            user,
            callback_data=ManageTrx.Callback(
                user_id=callback_data.user_id,
                trx_id=callback_data.trx_id,
                action=ManageTrxAction.show,
                current_page=callback_data.current_page,
            ),
        )
    await query.answer("Not Implemented", show_alert=True)


HELP_TEXT = generate_commands_help(sys.modules[__name__])


@router.message(Command("paycmd"), AdminAccess())
async def show_help_command(message: Message, user: User):
    """Show help message

    /paycmd

    Returns:
        Message: message of help text

    Example:
        /paycmd
    """
    for text in HELP_TEXT:
        await message.reply(text)
