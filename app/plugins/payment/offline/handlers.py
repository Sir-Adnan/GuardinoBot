"""Offline (manual) crypto gateway — customer flow + admin review.

Separate from ``offline.py`` (the lightweight Settings imported by
``app.utils.settings``) so its heavy imports don't create a cycle; loaded via the
plugin handlers list. Uses ``qmsg.bot`` / ``message.bot`` (no ``app.main`` import).

Flow: pick coin → show wallet + QR → customer sends TXID (and a screenshot if
required) → a pending ``CryptoPayment(offline)`` + Transaction(waiting) is created
and super-admins get an Approve/Reject card. **Approve** sets the transaction
``finished`` (balance = Σ finished ``amount``, so this is the only credit step) —
crediting NEVER happens automatically here. Reject marks it ``rejected``.
"""

import io
from datetime import datetime as dt
from typing import Literal

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app.keyboards import base
from app.keyboards.admin.admin import AdminPanel, AdminPanelAction, CancelFormAdmin
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.utils import helpers, settings
from app.utils.filters import IsSuperUser, SupportAccess

from .offline import SETTINGS_KEY_PREFIX

router = Router(name="payment/offline")

_UNAVAILABLE = (
    "📍 درحال حاضر امکان پرداختِ دستیِ ارز دیجیتال وجود ندارد! با پشتیبانی تماس بگیرید."
)


class OfflineForm(StatesGroup):
    custom_amount = State()  # awaiting a typed charge amount
    proof = State()  # awaiting TXID (+ optional screenshot)


class OfflineCoinCb(CallbackData, prefix="ofcoin"):
    code: str


class OfflineCancelCb(CallbackData, prefix="ofcancel"):
    pass


class OfflineReviewCb(CallbackData, prefix="ofrev"):
    action: Literal["approve", "reject", "reject_cancel"]
    cp_id: int
    confirmed: bool = False


class OfflineReviewKb(InlineKeyboardBuilder):
    """Stateful review buttons: drop ``approve`` once finished and ``reject``
    once rejected — so an admin can still **reject an already-approved** payment
    (reverses the credit + removes the subscription) or re-approve a rejected one."""

    def __init__(self, cp_id: int, status, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if status != Transaction.Status.finished:
            self.button(
                text="✅ تأیید",
                callback_data=OfflineReviewCb(action="approve", cp_id=cp_id),
            )
        if status != Transaction.Status.rejected:
            self.button(
                text="❌ رد",
                callback_data=OfflineReviewCb(action="reject", cp_id=cp_id),
            )
        self.adjust(2)


class OfflineRejectConfirmKb(InlineKeyboardBuilder):
    """Confirm step before rejecting an already-approved payment (it also removes
    the customer's subscription)."""

    def __init__(self, cp_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.button(
            text="✅ بله، حذف و رد کن",
            callback_data=OfflineReviewCb(
                action="reject", cp_id=cp_id, confirmed=True
            ),
        )
        self.button(
            text="↩️ انصراف",
            callback_data=OfflineReviewCb(action="reject_cancel", cp_id=cp_id),
        )
        self.adjust(1, 1)


def _qr_png(text: str) -> BufferedInputFile:
    from app.utils.qr import gen_qr  # lazy: app.utils.qr pulls app.main

    buf = io.BytesIO()
    gen_qr(text).make_image().save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="wallet.png")


# --- 0) charge-account entry: show the amount menu --------------------------
@router.message(
    F.text.in_([base.MainMenu.cancel, base.MainMenu.back]),
    ~CommandStart(),
    ~Command("menu"),
    StateFilter(OfflineForm.custom_amount),
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
    s = settings.get_settings()
    if not s.payment_offline.enabled or not s.payment_offline.enabled_coins():
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    text = (
        f"💠 پرداختِ دستیِ ارز دیجیتال — <b>{s.payment_offline.menu_title}</b>\n\n"
        f"مبلغ موردِنظر برای افزایش اعتبار را انتخاب کنید "
        f"(حداقل {s.payment_offline.min_pay_amount:,} تومان):"
    )
    markup = payment.SelectPayAmount(
        method=SETTINGS_KEY_PREFIX, _settings=s
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


# --- 0b) custom amount: prompt + capture ------------------------------------
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
    await state.set_state(OfflineForm.custom_amount)
    await query.message.answer(
        f"💴 مبلغ موردِنظر برای افزایش اعتبار را وارد کنید: (حداقل {min_pay_amount:,})",
        reply_markup=base.CancelUserForm(cancel=True).as_markup(
            resize_keyboard=True, one_time_keyboard=True
        ),
    )


@router.message(
    ~F.text.in_([CancelFormAdmin.cancel, base.MainMenu.main_menu]),
    ~CommandStart(),
    ~Command("menu"),
    OfflineForm.custom_amount,
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
    return await select_offline(
        message,
        user,
        callback_data=payment.SelectPayAmount.Callback(
            amount=amount, free=free, method=SETTINGS_KEY_PREFIX
        ),
        state=state,
    )


# --- 1) amount chosen: show the coin list -----------------------------------
@router.callback_query(payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX))
async def select_offline(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
    state: FSMContext,
):
    s = settings.get_settings().payment_offline
    coins = s.enabled_coins() if s.enabled else []
    if not coins:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(_UNAVAILABLE, show_alert=True)
        return await qmsg.answer(_UNAVAILABLE)
    await state.set_state(None)
    await state.update_data(
        amount=callback_data.amount,
        free=callback_data.free,
        direct_mode=callback_data.direct_mode,
        service_id=callback_data.service_id,
        proxy_id=callback_data.proxy_id,
        pending_txid=None,  # fresh proof session — clear any abandoned progress
        pending_shot=None,
    )
    kb = InlineKeyboardBuilder()
    for c in coins:
        kb.button(text=c.label, callback_data=OfflineCoinCb(code=c.code))
    kb.button(text="🔙 انصراف", callback_data=OfflineCancelCb())
    kb.adjust(1)
    text = "💠 ارزِ موردِنظر برای پرداخت را انتخاب کنید:"
    if isinstance(qmsg, CallbackQuery):
        await qmsg.message.edit_text(text, reply_markup=kb.as_markup())
        await qmsg.answer()
    else:
        await qmsg.answer(text, reply_markup=kb.as_markup())


# --- 2) coin selected: show wallet + QR, ask for the TXID --------------------
@router.callback_query(OfflineCoinCb.filter())
async def offline_coin(
    qmsg: CallbackQuery,
    user: User,
    callback_data: OfflineCoinCb,
    state: FSMContext,
):
    s = settings.get_settings().payment_offline
    coin = s.coin_by_code(callback_data.code)
    if not coin or not coin.enabled or not coin.address.strip():
        return await qmsg.answer("این ارز در دسترس نیست!", show_alert=True)
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        return await qmsg.answer("نشست منقضی شد؛ از منوی شارژ دوباره اقدام کنید.", show_alert=True)
    await state.update_data(coin_code=coin.code)
    await state.set_state(OfflineForm.proof)

    proof_hint = (
        "TXID (هشِ تراکنش) و <b>اسکرین‌شاتِ پرداخت</b> را ارسال کنید"
        if s.require_screenshot
        else "TXID (هشِ تراکنش) را ارسال کنید"
    )
    caption = (
        f"💠 ارز: <b>{coin.label}</b>\n"
        f"🌐 شبکه: <b>{coin.network}</b>\n\n"
        "آدرسِ کیف‌پول (برای کپی، روی آن بزنید):\n"
        f"<code>{coin.address}</code>\n\n"
        f"💰 معادلِ <b>{amount:,}</b> تومان را دقیق به این آدرس واریز کنید.\n\n"
        f"سپس {proof_hint} 👇\n"
        "<i>می‌توانید اسکرین‌شات را با کپشنِ TXID در یک پیام بفرستید.</i>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 انصراف", callback_data=OfflineCancelCb())
    await qmsg.message.answer_photo(
        _qr_png(coin.address), caption=caption, reply_markup=kb.as_markup()
    )
    await qmsg.answer()


# --- cancel -----------------------------------------------------------------
@router.callback_query(OfflineCancelCb.filter())
async def offline_cancel(qmsg: CallbackQuery, user: User, state: FSMContext):
    await state.clear()
    await qmsg.answer("لغو شد.")
    try:
        await qmsg.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


# --- 3) proof received: create the pending payment + notify admins ----------
@router.message(
    OfflineForm.proof,
    ~CommandStart(),
    ~Command(commands=["menu", "start", "cancel"]),
)
async def offline_proof(message: Message, user: User, state: FSMContext):
    s = settings.get_settings().payment_offline
    data = await state.get_data()
    # Accumulate across messages so order/splitting never traps the user: a text
    # message = the hash, a photo = the screenshot, a photo+caption = both. We
    # keep partial progress in the FSM and only proceed once everything required
    # is collected (avoids the "hash → asks screenshot → asks hash …" loop).
    txid = data.get("pending_txid")
    file_id = data.get("pending_shot")

    candidate = None  # a hash supplied by THIS message (text or photo caption)
    if message.photo:
        file_id = message.photo[-1].file_id
        if (message.caption or "").strip():
            candidate = message.caption.strip()
    elif (message.text or "").strip():
        candidate = message.text.strip()
    else:
        return await message.answer(
            "لطفاً <b>TXID</b> را به‌صورتِ متن، یا <b>اسکرین‌شات</b> را به‌صورتِ تصویر بفرستید."
        )

    if candidate is not None:
        if len(candidate) < 6 or len(candidate) > 128:
            await state.update_data(pending_shot=file_id)  # don't lose a screenshot
            return await message.answer(
                "TXID نامعتبر است؛ هشِ تراکنش را دوباره ارسال کنید."
            )
        txid = candidate

    await state.update_data(pending_txid=txid, pending_shot=file_id)

    # ask only for what is still missing — keeping what we already have
    if not txid:
        return await message.answer(
            "✅ دریافت شد. حالا <b>TXID</b> (هشِ تراکنش) را ارسال کنید 👇"
        )
    if s.require_screenshot and not file_id:
        return await message.answer(
            "✅ دریافت شد. حالا <b>اسکرین‌شاتِ پرداخت</b> را ارسال کنید (تصویر) 👇"
        )

    # everything required is in hand → build the pending payment
    coin = s.coin_by_code(data.get("coin_code"))
    amount = data.get("amount")
    free = int(data.get("free") or 0)
    if not coin or not amount:
        await state.clear()
        return await message.answer("نشست منقضی شد؛ از منوی شارژ دوباره اقدام کنید.")
    await state.clear()

    async with in_transaction():
        transaction = await Transaction.create(
            type=Transaction.PaymentType.crypto,
            status=Transaction.Status.waiting,
            amount=amount + free,
            amount_free_given=free,
            user=user,
        )
        if data.get("direct_mode"):
            mode = data["direct_mode"]
            invoice_type = (
                Invoice.Type.renew_now
                if mode == "renew"
                else Invoice.Type.renew_reserve
                if mode == "reserve"
                else Invoice.Type.purchase
            )
            await Invoice.create(
                amount=amount,
                type=invoice_type,
                is_paid=False,
                is_draft=True,
                service_id=data.get("service_id") or None,
                proxy_id=data.get("proxy_id") or None,
                user=user,
                transaction=transaction,
            )
        cp = await CryptoPayment.create(
            transaction=transaction,
            provider=CryptoPayment.Provider.offline,
            usdt_rate=0,
            price_amount=float(amount),
            price_currency="manual",
            payment_status=CryptoPayment.PaymentStatus.waiting,
            pay_currency=coin.code,
            pay_address=coin.address,
            extra_data={
                "coin_label": coin.label,
                "network": coin.network,
                "txid": txid,
                "screenshot": file_id,
            },
        )

    await message.answer(
        "✅ اطلاعاتِ پرداختِ شما ثبت شد و در حالِ بررسی است.\n"
        "پس از تأییدِ ادمین، اعتبار به‌صورتِ خودکار به حساب‌تان اضافه می‌شود."
    )

    # notify super-admins + support admins with a stateful approve/reject card
    kb = OfflineReviewKb(cp_id=cp.id, status=transaction.status)
    info = (
        "🪙 <b>پرداختِ آفلاینِ جدید — بررسی</b>\n\n"
        f"👤 کاربر: <code>{user.id}</code> {('@' + user.username) if user.username else ''}\n"
        f"💰 مبلغ: <b>{transaction.amount:,}</b> تومان\n"
        f"💠 ارز: {coin.label} ({coin.network})\n"
        f"🔗 TXID: <code>{txid}</code>\n"
        f"🧾 فاکتور: <code>{transaction.id}</code>"
    )
    dests = list(config.SUPER_USERS)
    support_ids = await User.filter(
        role=User.Role.support, is_blocked=False
    ).values_list("id", flat=True)
    dests += [i for i in support_ids if i not in dests]
    for uid in dests:
        try:
            if file_id:
                await message.bot.send_photo(uid, file_id, caption=info, reply_markup=kb.as_markup())
            else:
                await message.bot.send_message(uid, info, reply_markup=kb.as_markup())
        except Exception:  # noqa: BLE001 - one bad admin chat must not break the flow
            pass


# --- 4) admin review: approve (credit) / reject -----------------------------
OFFLINE_REVIEW_QUEUE = "offline:review:queue"  # web pushes here; bot drains it


async def _fetch_offline_cp(cp_id: int):
    return (
        await CryptoPayment.filter(
            id=cp_id, provider=CryptoPayment.Provider.offline
        )
        .prefetch_related("transaction")
        .first()
    )


async def _approve_offline(cp, bot, admin=None) -> str:
    """Credit + activate a pending offline payment. Idempotent (already-finished
    guard). Returns ``approved`` | ``already``."""
    transaction = cp.transaction
    if transaction.status == Transaction.Status.finished:
        return "already"
    async with in_transaction():
        transaction.status = Transaction.Status.finished
        transaction.finished_at = dt.now()
        transaction.amount_paid = transaction.amount - transaction.amount_free_given
        await transaction.save()
        cp.payment_status = CryptoPayment.PaymentStatus.finished
        await cp.save()
    from app.plugins.payment import jobs  # local: credit/activation flow

    msg = None
    try:
        msg = await bot.send_message(
            transaction.user_id,
            f"✅ پرداختِ آفلاینِ شما تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!\n"
            f"🧾 فاکتور: <code>{transaction.id}</code>",
        )
    except Exception:  # noqa: BLE001
        pass
    helpers.transaction_log(transaction=transaction, payment=cp, admin=admin)
    jobs.activate_service(transaction, msg)
    return "approved"


async def _reject_offline(cp, bot, admin=None) -> tuple[str, str]:
    """Reject a pending offline payment, or REVERSE an already-approved one —
    undo the credit + remove the activated subscription (panel + bot) via
    ``revoke_activated_transaction`` (same helper the card-to-card reject uses).
    Idempotent. Returns ``(result, summary)`` where result is
    ``rejected`` | ``reverted`` | ``already_rejected``."""
    transaction = cp.transaction
    if transaction.status == Transaction.Status.rejected:
        return "already_rejected", ""
    was_activated = transaction.status == Transaction.Status.finished
    # local import: avoid an import cycle on the jobs module
    from app.plugins.payment.jobs import revoke_activated_transaction

    # sets the tx to ``rejected`` (removes the credit) and, for an activated
    # purchase, deletes the proxy + invoice so the balance nets back to ~0
    summary = await revoke_activated_transaction(transaction)
    cp.payment_status = CryptoPayment.PaymentStatus.failed
    await cp.save()
    try:
        if was_activated:
            await bot.send_message(
                transaction.user_id,
                f"❌ پرداختِ آفلاینِ شما (فاکتور <code>{transaction.id}</code>) رد شد و اشتراکِ مربوطه لغو شد.\n"
                "برای اطلاعاتِ بیشتر با پشتیبانی تماس بگیرید.",
            )
        else:
            await bot.send_message(
                transaction.user_id,
                f"❌ پرداختِ آفلاینِ شما (فاکتور <code>{transaction.id}</code>) رد شد.\n"
                "اگر مبلغی واریز کرده‌اید، با پشتیبانی تماس بگیرید.",
            )
    except Exception:  # noqa: BLE001
        pass
    helpers.transaction_log(
        transaction=transaction,
        payment=cp,
        admin=admin,
        note="پرداخت قبلاً تأیید و اشتراک فعال شده بود؛ فعال‌سازی لغو شد."
        if was_activated
        else None,
    )
    return ("reverted" if was_activated else "rejected"), summary


async def apply_offline_review(cp, action: str, bot, admin=None) -> str:
    """Single credit/reverse path shared by the bot's inline review and the
    web→Redis queue. Idempotent. Returns a short status code."""
    if cp is None:
        return "notfound"
    if action == "approve":
        return await _approve_offline(cp, bot, admin=admin)
    result, _ = await _reject_offline(cp, bot, admin=admin)
    return result


async def process_offline_review_queue(bot) -> None:
    """Drain web-submitted reviews (the API rpushes JSON to the Redis list) and
    apply them in the BOT process so user-notify + service-activation run.
    Called from the 15s sync poll."""
    import json

    from app.main import redis  # bot-process redis

    for _ in range(50):  # bounded drain per tick
        raw = await redis.lpop(OFFLINE_REVIEW_QUEUE)
        if not raw:
            break
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            item = json.loads(raw)
            cp_id = int(item["cp_id"])
            action = "approve" if item.get("action") == "approve" else "reject"
        except Exception:  # noqa: BLE001
            continue
        await apply_offline_review(
            await _fetch_offline_cp(cp_id), action, bot, admin="🖥 پنل وب"
        )


async def _rerender_card(qmsg: CallbackQuery, cp_id: int, status) -> None:
    """Swap the card's keyboard to reflect the new status (robust for both photo
    and text cards — never edit_text a photo card)."""
    try:
        await qmsg.message.edit_reply_markup(
            reply_markup=OfflineReviewKb(cp_id, status).as_markup()
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(OfflineReviewCb.filter(F.action == "approve"), SupportAccess())
async def offline_approve(
    qmsg: CallbackQuery, user: User, callback_data: OfflineReviewCb
):
    cp = await _fetch_offline_cp(callback_data.cp_id)
    if cp is None:
        return await qmsg.answer("پرداخت یافت نشد!", show_alert=True)
    result = await _approve_offline(cp, qmsg.bot, admin=user)
    if result == "already":
        return await qmsg.answer("این پرداخت قبلاً تأیید شده است.", show_alert=True)
    await qmsg.answer("تأیید شد ✅", show_alert=True)
    await cp.transaction.refresh_from_db()
    await _rerender_card(qmsg, cp.id, cp.transaction.status)


@router.callback_query(
    OfflineReviewCb.filter(F.action == "reject_cancel"), SupportAccess()
)
async def offline_reject_cancel(
    qmsg: CallbackQuery, user: User, callback_data: OfflineReviewCb
):
    """Cancel the reject confirmation: restore the normal review keyboard."""
    cp = await _fetch_offline_cp(callback_data.cp_id)
    if cp is None:
        return await qmsg.answer("پرداخت یافت نشد!", show_alert=True)
    await _rerender_card(qmsg, cp.id, cp.transaction.status)
    return await qmsg.answer("لغو شد")


@router.callback_query(OfflineReviewCb.filter(F.action == "reject"), SupportAccess())
async def offline_reject(
    qmsg: CallbackQuery, user: User, callback_data: OfflineReviewCb
):
    cp = await _fetch_offline_cp(callback_data.cp_id)
    if cp is None:
        return await qmsg.answer("پرداخت یافت نشد!", show_alert=True)
    transaction = cp.transaction
    if transaction.status == Transaction.Status.rejected:
        return await qmsg.answer("این پرداخت قبلاً رد شده است.", show_alert=True)

    # already approved → rejecting now also removes the subscription, so confirm
    # first (a waiting receipt has nothing to undo, so it rejects in one tap).
    was_activated = transaction.status == Transaction.Status.finished
    if was_activated and not callback_data.confirmed:
        await qmsg.answer(
            "⚠️ این پرداخت قبلاً تأیید شده و اشتراک ساخته شده! با رد کردن، اشتراکِ کاربر حذف و فاکتور باطل می‌شود.",
            show_alert=True,
        )
        try:
            await qmsg.message.edit_reply_markup(
                reply_markup=OfflineRejectConfirmKb(cp.id).as_markup()
            )
        except Exception:  # noqa: BLE001
            pass
        return

    _, summary = await _reject_offline(cp, qmsg.bot, admin=user)
    await qmsg.answer("رد شد", show_alert=True)
    await transaction.refresh_from_db()
    await _rerender_card(qmsg, cp.id, transaction.status)
    if was_activated and summary:
        try:
            await qmsg.message.reply(f"🧾 نتیجهٔ لغو فعال‌سازی:\n{summary}")
        except Exception:  # noqa: BLE001
            pass


# --- in-bot admin settings (⚙️ → تنظیمات → درگاه‌ها) -------------------------
# Wallets/coins are configured in the WEB panel; in the bot we only show a
# summary + an enable/disable toggle so the button is never dead.
def _settings_kb(s) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=(
            "🟢 فعال — برای غیرفعال‌کردن بزنید"
            if s.enabled
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
    s = settings.get_settings().payment_offline
    n_coins = len(s.enabled_coins())
    text = (
        "💠 <b>درگاهِ پرداختِ دستیِ ارز دیجیتال</b>\n\n"
        f"وضعیت: <b>{'فعال ✅' if s.enabled else 'غیرفعال ❌'}</b>\n"
        f"نام در منو: <b>{s.menu_title}</b>\n"
        f"کیف‌پول‌های فعال: <code>{n_coins}</code>\n"
        f"حداقل مبلغ: <code>{s.min_pay_amount:,}</code> تومان\n"
        f"الزامِ اسکرین‌شات: {'بله' if s.require_screenshot else 'خیر'}\n\n"
        "ℹ️ آدرسِ کیف‌پول‌ها و تنظیماتِ کامل از <b>پنلِ وب</b> انجام می‌شود."
    )
    await qmsg.message.edit_text(
        text, reply_markup=_settings_kb(s).as_markup(), disable_web_page_preview=True
    )


@router.callback_query(F.data == f"pm:toggle:{SETTINGS_KEY_PREFIX}", IsSuperUser())
async def toggle_settings(qmsg: CallbackQuery, user: User):
    s = settings.get_settings().payment_offline
    if not s.enabled and not s.enabled_coins():
        return await qmsg.answer(
            "ابتدا حداقل یک کیف‌پولِ فعال در پنلِ وب اضافه کنید.", show_alert=True
        )
    s.enabled = not s.enabled
    await settings.Settings.update(payment_offline=s)
    await settings.reload_settings()
    await qmsg.answer("به‌روزرسانی شد ✅")
    await show_settings(qmsg, user)
