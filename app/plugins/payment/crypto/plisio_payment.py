"""Plisio charge-flow handler.

Kept SEPARATE from ``plisio.py`` (which holds the client + Settings and is
imported by ``app.utils.settings``) so this module's heavy imports
(``app.utils.settings``, models, keyboards) don't create a settings↔plisio
import cycle. Mirrors the NowPayments flow end-to-end: charge-account entry →
amount menu → (preset or custom amount) → create a Transaction + a hosted Plisio
invoice and show the pay link. Crediting happens in ``crypto/views.py`` on the
signature-verified IPN — never here.
"""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.filters.command import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.plugins.payment.clients import CouldNotGetUSDTPrice, NobitexMarketAPI
from app.utils import settings
from app.utils.filters import IsSuperUser

from .plisio import SETTINGS_KEY_PREFIX, PlisioAPI, PlisioError

router = Router(name="payment/plisio")

_UNAVAILABLE = (
    "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
)
_RATE_ERR = "📍 خطایی در دریافت نرخ ارز رخ داد! لطفا با پشتیبانی تماس بگیرید."


class PlisioCustomAmountForm(StatesGroup):
    amount = State()


class PayUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(text="💳 پرداخت", url=url)


# --- 1) charge-account entry: show the amount menu --------------------------
@router.message(
    F.text.in_([base.MainMenu.cancel, base.MainMenu.back]),
    ~CommandStart(),
    ~Command("menu"),
    StateFilter(PlisioCustomAmountForm),
)
@router.callback_query(
    payment.ChargePanel.Callback.filter(F.method == SETTINGS_KEY_PREFIX)
)
async def charge(qmsg: CallbackQuery | Message, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer("🌀 عملیات لغو شد!")
        else:
            await qmsg.answer("🌀 عملیات لغو شد!", reply_markup=ReplyKeyboardRemove())
    _settings = settings.get_settings()
    ps = _settings.payment_plisio
    if not ps.enabled or not ps.api_key:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    text = (
        f"💎 افزایش اعتبار با <b>{ps.menu_title}</b>\n\n"
        f"مبلغ موردِنظر را انتخاب کنید (حداقل {ps.min_pay_amount:,} تومان):"
    )
    markup = payment.SelectPayAmount(
        method=SETTINGS_KEY_PREFIX, _settings=_settings
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


# --- 2) custom amount: prompt for a typed value -----------------------------
@router.callback_query(
    payment.SelectPayAmount.Callback.filter(
        (F.amount == 0) & (F.method == SETTINGS_KEY_PREFIX)
    )
)
async def custom_amount(
    query: CallbackQuery,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
    state: FSMContext,
):
    _settings = settings.get_settings()
    min_pay_amount, _, _ = payment.get_payment_variables(
        callback_data.method, _settings
    )
    await state.set_state(PlisioCustomAmountForm.amount)
    await state.set_data({"method": callback_data.method})
    await query.message.answer(
        f"💴 مبلغ موردِنظر برای افزایش اعتبار را وارد کنید: (حداقل {min_pay_amount:,})",
        reply_markup=base.CancelUserForm(cancel=True).as_markup(
            resize_keyboard=True, one_time_keyboard=True
        ),
    )


# --- 3) custom amount: capture the typed value ------------------------------
@router.message(
    ~F.text.in_([CancelFormAdmin.cancel, base.MainMenu.main_menu]),
    ~CommandStart(),
    ~Command("menu"),
    PlisioCustomAmountForm.amount,
)
async def get_custom_amount(message: Message, user: User, state: FSMContext):
    try:
        amount = int(message.text)
    except (ValueError, TypeError):
        return await message.reply("❌ لطفا مقداری عددی وارد کنید:")
    _settings = settings.get_settings()
    min_pay_amount, free_after, free_after_percent = payment.get_payment_variables(
        SETTINGS_KEY_PREFIX, _settings
    )
    if amount < min_pay_amount:
        return await message.reply(
            f"❌ لطفا مقداری بیشتر از {min_pay_amount:,} وارد کنید:"
        )
    free = int(
        0
        if (not free_after) or (amount < free_after)
        else amount * (free_after_percent / 100)
    )
    await state.clear()
    return await select_amount(
        message,
        user,
        callback_data=payment.SelectPayAmount.Callback(
            amount=amount, free=free, method=SETTINGS_KEY_PREFIX
        ),
    )


# --- 4) create the transaction + hosted Plisio invoice ----------------------
@router.callback_query(
    payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX)
)
async def select_amount(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
):
    _settings = settings.get_settings().payment_plisio
    if not _settings.enabled or not _settings.api_key:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)

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
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text=text, reply_markup=markup)
        return await qmsg.answer(text=text, reply_markup=markup)
    except PlisioError:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    except CouldNotGetUSDTPrice:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_RATE_ERR, show_alert=True)
        return await qmsg.answer(_RATE_ERR)


# --- in-bot admin settings (⚙️ → تنظیمات → درگاه‌ها) -------------------------
# Full config (API key / allowed coins) lives in the WEB panel; in the bot we
# only show a summary + an enable/disable toggle so the button is never dead.
def _settings_kb(ps) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=(
            "🟢 فعال — برای غیرفعال‌کردن بزنید"
            if ps.enabled
            else "🔴 غیرفعال — برای فعال‌کردن بزنید"
        ),
        callback_data=f"pm:toggle:{SETTINGS_KEY_PREFIX}",
    )
    kb.button(
        text="🔙 برگشت",
        callback_data=AdminPanel.Callback(action=AdminPanelAction.settings),
    )
    kb.adjust(1)
    return kb


@router.callback_query(F.data == f"pm:settings:{SETTINGS_KEY_PREFIX}", IsSuperUser())
async def show_settings(qmsg: CallbackQuery, user: User):
    ps = settings.get_settings().payment_plisio
    coins = ", ".join(ps.allowed_coins) if ps.allowed_coins else "همه"
    text = (
        "💎 <b>درگاهِ Plisio</b>\n\n"
        f"وضعیت: <b>{'فعال ✅' if ps.enabled else 'غیرفعال ❌'}</b>\n"
        f"نام در منو: <b>{ps.menu_title}</b>\n"
        f"کلیدِ API: {'ثبت‌شده ✅' if ps.api_key else 'خالی ❌'}\n"
        f"حداقل مبلغ: <code>{ps.min_pay_amount:,}</code> تومان\n"
        f"کوین‌های مجاز: <code>{coins}</code>\n\n"
        "ℹ️ تنظیماتِ کامل (کلیدِ API و کوین‌ها) از <b>پنلِ وب</b> انجام می‌شود."
    )
    await qmsg.message.edit_text(
        text, reply_markup=_settings_kb(ps).as_markup(), disable_web_page_preview=True
    )


@router.callback_query(F.data == f"pm:toggle:{SETTINGS_KEY_PREFIX}", IsSuperUser())
async def toggle_settings(qmsg: CallbackQuery, user: User):
    ps = settings.get_settings().payment_plisio
    if not ps.enabled and not ps.api_key:
        return await qmsg.answer(
            "ابتدا کلیدِ API را در پنلِ وب ثبت کنید.", show_alert=True
        )
    ps.enabled = not ps.enabled
    await settings.Settings.update(payment_plisio=ps)
    await settings.reload_settings()
    await qmsg.answer("به‌روزرسانی شد ✅")
    await show_settings(qmsg, user)
