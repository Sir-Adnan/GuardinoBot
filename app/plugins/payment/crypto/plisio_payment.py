"""Plisio charge-flow handler."""

from typing import Literal

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.filters.command import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app.logger import get_logger
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.premium import premium_button
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.utils import settings
from app.utils.filters import IsSuperUser

from .plisio import SETTINGS_KEY_PREFIX, PlisioAPI, PlisioError, display_currency
from .plisio_service import finalize_plisio_payment
from .rates import PaymentRateError, calculate_payable_usdt, get_usdt_toman_rate

router = Router(name="payment/plisio")
logger = get_logger("payment/plisio")

_UNAVAILABLE = (
    "📍 درحال حاضر امکان پرداخت ارز دیجیتال وجود ندارد! لطفا با پشتیبانی تماس بگیرید."
)
_RATE_ERR = (
    "📍 خطایی در دریافت نرخ تتر رخ داد. لطفا چند دقیقه دیگر دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
)


class PlisioCustomAmountForm(StatesGroup):
    amount = State()


class PlisioInvoiceAction(CallbackData, prefix="plisact"):
    action: Literal["check", "cancel"]
    transaction_id: int


class PayUrl(InlineKeyboardBuilder):
    def __init__(self, url: str, transaction_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add(
            premium_button(
                text="💳 پرداخت آنلاین",
                key="plisio_pay_online",
                url=url,
            )
        )
        self.add(
            premium_button(
                text="🔄 بررسی وضعیت پرداخت",
                key="plisio_check_payment",
                callback_data=PlisioInvoiceAction(
                    action="check", transaction_id=transaction_id
                ),
            )
        )
        self.add(
            premium_button(
                text="❌ لغو فاکتور",
                key="plisio_cancel_invoice",
                callback_data=PlisioInvoiceAction(
                    action="cancel", transaction_id=transaction_id
                ),
            )
        )
        self.adjust(1)


def _format_decimal(value) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _short_currency_list(codes: list[str]) -> str:
    labels = [display_currency(code) for code in codes[:4]]
    if len(codes) > 4:
        labels.append(f"{len(codes) - 4} گزینه دیگر")
    return "، ".join(labels)


def _direct_invoice_type(mode: str | None):
    if mode == "renew":
        return Invoice.Type.renew_now
    if mode == "reserve":
        return Invoice.Type.renew_reserve
    return Invoice.Type.purchase


@router.message(
    F.text.in_([base.MainMenu.cancel, base.MainMenu.back]),
    ~CommandStart(),
    ~Command("menu"),
    StateFilter(PlisioCustomAmountForm),
)
@router.callback_query(payment.ChargePanel.Callback.filter(F.method == SETTINGS_KEY_PREFIX))
async def charge(qmsg: CallbackQuery | Message, user: User, state: FSMContext = None):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer("🌐 عملیات لغو شد!")
        else:
            await qmsg.answer("🌐 عملیات لغو شد!", reply_markup=ReplyKeyboardRemove())
    _settings = settings.get_settings()
    ps = _settings.payment_plisio
    if not ps.enabled or not ps.api_key:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    text = (
        f"💎 افزایش اعتبار با <b>{ps.menu_title}</b>\n\n"
        f"مبلغ موردنظر را انتخاب کنید (حداقل {ps.min_pay_amount:,} تومان):"
    )
    markup = payment.SelectPayAmount(
        method=SETTINGS_KEY_PREFIX, _settings=_settings
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


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
        f"💴 مبلغ موردنظر برای افزایش اعتبار را وارد کنید: (حداقل {min_pay_amount:,})",
        reply_markup=base.CancelUserForm(cancel=True).as_markup(
            resize_keyboard=True, one_time_keyboard=True
        ),
    )


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


@router.callback_query(payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX))
async def select_amount(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
):
    ps = settings.get_settings().payment_plisio
    if not ps.enabled or not ps.api_key:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)

    await qmsg.answer("♻️ درحال پردازش! لطفا کمی منتظر بمانید...")
    try:
        usdt_rate = await get_usdt_toman_rate(ps)
        payable_usdt = calculate_payable_usdt(
            callback_data.amount, usdt_rate, ps.usdt_margin_percent
        )
        currencies = ps.currency_codes()
        invoice_currency = ps.invoice_currency()
        preferred_currency = ps.default_currency
        if invoice_currency not in currencies:
            currencies.insert(0, invoice_currency)
        public_base = config.PUBLIC_BASE_URL

        async with in_transaction():
            transaction = await Transaction.create(
                type=Transaction.PaymentType.crypto,
                status=Transaction.Status.waiting,
                amount=callback_data.amount + callback_data.free,
                amount_free_given=callback_data.free,
                user=user,
            )
            if callback_data.direct_mode is not None:
                await Invoice.create(
                    amount=callback_data.amount,
                    type=_direct_invoice_type(callback_data.direct_mode),
                    is_paid=False,
                    is_draft=True,
                    service_id=callback_data.service_id or None,
                    proxy_id=callback_data.proxy_id or None,
                    user=user,
                    transaction=transaction,
                )

            inv = await PlisioAPI.create_invoice(
                api_key=ps.api_key,
                api_base=ps.api_base,
                order_number=str(transaction.id),
                order_name=f"GuardinoBot #{transaction.id}",
                description=f"GuardinoBot payment #{transaction.id}",
                currency=invoice_currency,
                amount=payable_usdt,
                allowed_psys_cids=",".join(currencies),
                callback_url=f"{public_base}/payments/plisio/callback?json=true",
                success_invoice_url=f"{public_base}/payments/plisio/success",
                fail_invoice_url=f"{public_base}/payments/plisio/fail",
                expire_min=ps.expire_min,
                return_existing=ps.return_existing,
            )
            invoice_url = inv["invoice_url"]
            txn_id = str(inv["txn_id"])
            tracking_code = f"GB-{transaction.id}"
            await CryptoPayment.create(
                transaction=transaction,
                provider=CryptoPayment.Provider.plisio,
                usdt_rate=int(usdt_rate),
                invoice_id=txn_id,
                payment_id=txn_id,
                order_id=str(transaction.id),
                price_amount=float(payable_usdt),
                price_currency=invoice_currency,
                pay_currency=invoice_currency,
                order_description=tracking_code,
                payment_status=CryptoPayment.PaymentStatus.waiting,
                extra_data={
                    "invoice_url": invoice_url,
                    "tracking_code": tracking_code,
                    "rate": str(usdt_rate),
                    "margin_percent": str(ps.usdt_margin_percent),
                    "raw_create_response": inv.get("_raw"),
                    "invoice_currency": invoice_currency,
                    "invoice_currency_label": display_currency(invoice_currency),
                    "preferred_currency": preferred_currency,
                    "allowed_currencies": currencies,
                    "allowed_currency_labels": [display_currency(c) for c in currencies],
                    "payable_usdt": str(payable_usdt),
                    "status_source": "created",
                },
            )

        toman = transaction.amount - transaction.amount_free_given
        allowed_text = _short_currency_list(currencies)
        text = f"""
🧾 <b>فاکتور پرداخت امن</b>

سرویس/شارژ: <b>{ps.menu_title}</b>
کد پیگیری: <code>GB-{transaction.id}</code>
شناسه Plisio: <code>{txn_id}</code>

مبلغ سفارش: <b>{toman:,}</b> تومان
مبلغ مبنا در درگاه: <b>{_format_decimal(payable_usdt)}</b> USDT
نرخ محاسبه: <b>{int(usdt_rate):,}</b> تومان

ارزهای قابل پرداخت: <b>{allowed_text}</b>

اعتبار فاکتور: <b>{ps.expire_min}</b> دقیقه

در صفحه Plisio می‌توانید یکی از ارزهای مجاز را انتخاب کنید؛ مبلغ معادل همان‌جا محاسبه می‌شود.
بعد از پرداخت، ربات به‌صورت خودکار وضعیت را بررسی می‌کند. اگر تایید با تاخیر انجام شد، کد پیگیری بالا را برای پشتیبانی ارسال کنید.
"""
        markup = PayUrl(url=invoice_url, transaction_id=transaction.id).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text=text, reply_markup=markup)
        return await qmsg.answer(text=text, reply_markup=markup)
    except PaymentRateError:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_RATE_ERR, show_alert=True)
        return await qmsg.answer(_RATE_ERR)
    except PlisioError:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    except Exception:  # noqa: BLE001
        logger.exception("plisio invoice flow failed")
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)


@router.callback_query(PlisioInvoiceAction.filter(F.action == "check"))
async def check_invoice(
    query: CallbackQuery,
    user: User,
    callback_data: PlisioInvoiceAction,
):
    transaction = await Transaction.filter(id=callback_data.transaction_id).first()
    if not transaction or transaction.user_id != user.id:
        return await query.answer("فاکتور پیدا نشد.", show_alert=True)
    if transaction.status == Transaction.Status.finished:
        return await query.answer("پرداخت قبلا تأیید شده است ✅", show_alert=True)
    await transaction.fetch_related("crypto_payment")
    cp = transaction.crypto_payment
    txn_id = cp.payment_id or cp.invoice_id
    ps = settings.get_settings().payment_plisio
    if not ps.api_key or not txn_id:
        return await query.answer(_UNAVAILABLE, show_alert=True)
    try:
        operation = await PlisioAPI.get_operation(
            txn_id, api_key=ps.api_key, api_base=ps.api_base
        )
        result = await finalize_plisio_payment(
            transaction, operation, source="manual_check"
        )
    except PlisioError:
        return await query.answer(
            "امکان بررسی وضعیت پرداخت در این لحظه وجود ندارد.", show_alert=True
        )

    if result["result"] in {"completed", "already_finished"}:
        return await query.answer("پرداخت تأیید شد ✅", show_alert=True)
    if result["result"] == "pending":
        return await query.answer(
            "پرداخت هنوز در انتظار تأیید شبکه است.", show_alert=True
        )
    if result["result"] == "failed":
        return await query.answer(
            "پرداخت ناموفق، منقضی یا نامتناظر ثبت شده است.", show_alert=True
        )
    return await query.answer("وضعیت پرداخت نامشخص است؛ با پشتیبانی تماس بگیرید.", show_alert=True)


@router.callback_query(PlisioInvoiceAction.filter(F.action == "cancel"))
async def cancel_invoice(
    query: CallbackQuery,
    user: User,
    callback_data: PlisioInvoiceAction,
):
    transaction = await Transaction.filter(id=callback_data.transaction_id).first()
    if not transaction or transaction.user_id != user.id:
        return await query.answer("فاکتور پیدا نشد.", show_alert=True)
    if transaction.status == Transaction.Status.finished:
        return await query.answer("این فاکتور قبلا پرداخت و تأیید شده است.", show_alert=True)
    await Transaction.filter(id=transaction.id).update(status=Transaction.Status.canceled)
    await CryptoPayment.filter(transaction_id=transaction.id).update(
        payment_status=CryptoPayment.PaymentStatus.failed,
    )
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    return await query.answer("فاکتور لغو شد.", show_alert=True)


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
    coins = _short_currency_list(ps.currency_codes()) if ps.currency_codes() else "همه"
    invoice_currency = ps.invoice_currency()
    text = (
        "💎 <b>درگاه Plisio</b>\n\n"
        f"وضعیت: <b>{'فعال ✅' if ps.enabled else 'غیرفعال ❌'}</b>\n"
        f"نام در منو: <b>{ps.menu_title}</b>\n"
        f"کلید API: {'ثبت‌شده ✅' if ps.api_key else 'خالی ❌'}\n"
        f"حداقل مبلغ: <code>{ps.min_pay_amount:,}</code> تومان\n"
        f"ارز مبنای فاکتور: <b>{display_currency(invoice_currency)}</b>\n"
        f"ارزهای قابل پرداخت: <b>{coins}</b>\n\n"
        "ℹ️ تنظیمات کامل از پنل وب انجام می‌شود."
    )
    await qmsg.message.edit_text(
        text, reply_markup=_settings_kb(ps).as_markup(), disable_web_page_preview=True
    )


@router.callback_query(F.data == f"pm:toggle:{SETTINGS_KEY_PREFIX}", IsSuperUser())
async def toggle_settings(qmsg: CallbackQuery, user: User):
    ps = settings.get_settings().payment_plisio
    if not ps.enabled and not ps.api_key:
        return await qmsg.answer(
            "ابتدا کلید API را در پنل وب ثبت کنید.", show_alert=True
        )
    ps.enabled = not ps.enabled
    await settings.Settings.update(payment_plisio=ps)
    await settings.reload_settings()
    await qmsg.answer("به‌روزرسانی شد ✅")
    await show_settings(qmsg, user)
