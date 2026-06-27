"""Plisio charge-flow handler.

Kept SEPARATE from ``plisio.py`` (which holds the client + Settings and is
imported by ``app.utils.settings``) so this module's heavy imports
(``app.utils.settings``, models, keyboards) don't create a settings↔plisio
import cycle. Mirrors the NowPayments flow: on the Plisio pay-amount callback,
create a Transaction + a hosted Plisio invoice and show the pay link. Crediting
happens in ``crypto/views.py`` on the signature-verified IPN — never here.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.plugins.payment.clients import CouldNotGetUSDTPrice, NobitexMarketAPI
from app.utils import settings

from .plisio import SETTINGS_KEY_PREFIX, PlisioAPI, PlisioError

router = Router(name="payment/plisio")

_UNAVAILABLE = (
    "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
)


class PayUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="💳 پرداخت", url=url)


@router.callback_query(
    payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX)
)
async def select_amount(
    qmsg: CallbackQuery,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
):
    _settings = settings.get_settings().payment_plisio
    if not _settings.enabled or not _settings.api_key:
        return await qmsg.answer(_UNAVAILABLE, show_alert=True)

    await qmsg.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        async with in_transaction():
            usdt_rate = await NobitexMarketAPI.get_price()
            transaction = await Transaction.create(
                type=Transaction.PaymentType.crypto,
                status=Transaction.Status.waiting,
                amount=callback_data.amount + callback_data.free,
                amount_free_given=callback_data.free,
                user=user,
            )
            if callback_data.direct_mode is not None:
                if callback_data.direct_mode == "renew":
                    invoice_type = Invoice.Type.renew_now
                elif callback_data.direct_mode == "reserve":
                    invoice_type = Invoice.Type.renew_reserve
                else:
                    invoice_type = Invoice.Type.purchase
                await Invoice.create(
                    amount=callback_data.amount,
                    type=invoice_type,
                    is_paid=False,
                    is_draft=True,
                    service_id=callback_data.service_id or None,
                    proxy_id=callback_data.proxy_id or None,
                    user=user,
                    transaction=transaction,
                )
            # fiat (USD) priced — Plisio converts to the coin the customer picks
            usd_amount = round(callback_data.amount / usdt_rate, 2)
            inv = await PlisioAPI.create_invoice(
                api_key=_settings.api_key,
                order_number=str(transaction.id),
                order_name=f"Charge #{transaction.id}",
                source_amount=usd_amount,
                source_currency="USD",
                callback_url=config.WEBHOOK_BASE_URL + "/plisio",
                allowed_psys_cids=(_settings.allowed_coins or None),
            )
            invoice_url = inv.get("invoice_url")
            if not invoice_url:
                raise PlisioError("Plisio returned no invoice_url")
            await CryptoPayment.create(
                transaction=transaction,
                provider=CryptoPayment.Provider.plisio,
                usdt_rate=usdt_rate,
                invoice_id=str(inv.get("txn_id") or ""),
                order_id=str(transaction.id),
                price_amount=usd_amount,
                price_currency="USD",
            )
        toman = transaction.amount - transaction.amount_free_given
        text = (
            f"✔️ شما در حال افزایش اعتبار با <b>{_settings.menu_title}</b> هستید!\n\n"
            f"💳 شماره فاکتور: <code>{transaction.id}</code>\n"
            f"💰 مبلغ: <b>{toman:,}</b> تومان (~${usd_amount})\n\n"
            "برای پرداخت روی دکمهٔ زیر بزنید 👇\n"
            "پس از تأییدِ پرداخت، اعتبار به‌صورت خودکار اضافه می‌شود."
        )
        markup = PayUrl(url=invoice_url).as_markup()
        return await qmsg.message.edit_text(text=text, reply_markup=markup)
    except PlisioError:
        return await qmsg.answer(_UNAVAILABLE, show_alert=True)
    except CouldNotGetUSDTPrice:
        return await qmsg.answer(
            "📍 خطایی در دریافت نرخ ارز رخ داد! لطفا با پشتیبانی تماس بگیرید.",
            show_alert=True,
        )
