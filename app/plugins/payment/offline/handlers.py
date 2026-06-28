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
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.transactions import in_transaction

import config
from app.keyboards.user import payment
from app.models.user import CryptoPayment, Invoice, Transaction, User
from app.utils import helpers, settings
from app.utils.filters import IsSuperUser

from .offline import SETTINGS_KEY_PREFIX

router = Router(name="payment/offline")

_UNAVAILABLE = (
    "📍 درحال حاضر امکان پرداختِ دستیِ ارز دیجیتال وجود ندارد! با پشتیبانی تماس بگیرید."
)


class OfflineForm(StatesGroup):
    proof = State()  # awaiting TXID (+ optional screenshot)


class OfflineCoinCb(CallbackData, prefix="ofcoin"):
    code: str


class OfflineCancelCb(CallbackData, prefix="ofcancel"):
    pass


class OfflineReviewCb(CallbackData, prefix="ofrev"):
    action: Literal["approve", "reject"]
    cp_id: int


def _qr_png(text: str) -> BufferedInputFile:
    from app.utils.qr import gen_qr  # lazy: app.utils.qr pulls app.main

    buf = io.BytesIO()
    gen_qr(text).make_image().save(buf, format="PNG")
    return BufferedInputFile(buf.getvalue(), filename="wallet.png")


# --- 1) method selected: show the coin list ---------------------------------
@router.callback_query(payment.SelectPayAmount.Callback.filter(F.method == SETTINGS_KEY_PREFIX))
async def select_offline(
    qmsg: CallbackQuery,
    user: User,
    callback_data: payment.SelectPayAmount.Callback,
    state: FSMContext,
):
    s = settings.get_settings().payment_offline
    coins = s.enabled_coins() if s.enabled else []
    if not coins:
        return await qmsg.answer(_UNAVAILABLE, show_alert=True)
    await state.set_state(None)
    await state.update_data(
        amount=callback_data.amount,
        free=callback_data.free,
        direct_mode=callback_data.direct_mode,
        service_id=callback_data.service_id,
        proxy_id=callback_data.proxy_id,
    )
    kb = InlineKeyboardBuilder()
    for c in coins:
        kb.button(text=c.label, callback_data=OfflineCoinCb(code=c.code))
    kb.button(text="🔙 انصراف", callback_data=OfflineCancelCb())
    kb.adjust(1)
    await qmsg.message.edit_text(
        "💠 ارزِ موردِنظر برای پرداخت را انتخاب کنید:", reply_markup=kb.as_markup()
    )
    await qmsg.answer()


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
    txid = (message.caption or message.text or "").strip()
    file_id = message.photo[-1].file_id if message.photo else None

    if not txid:
        return await message.answer("لطفاً <b>TXID</b> (هشِ تراکنش) را به‌صورتِ متن یا کپشنِ تصویر بفرستید.")
    if len(txid) < 6 or len(txid) > 128:
        return await message.answer("TXID نامعتبر است؛ دوباره ارسال کنید.")
    if s.require_screenshot and not file_id:
        return await message.answer("لطفاً <b>اسکرین‌شاتِ پرداخت</b> را هم ارسال کنید (تصویر).")

    data = await state.get_data()
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

    # notify super-admins with an approve/reject card
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تأیید", callback_data=OfflineReviewCb(action="approve", cp_id=cp.id))
    kb.button(text="❌ رد", callback_data=OfflineReviewCb(action="reject", cp_id=cp.id))
    kb.adjust(2)
    info = (
        "🪙 <b>پرداختِ آفلاینِ جدید — بررسی</b>\n\n"
        f"👤 کاربر: <code>{user.id}</code> {('@' + user.username) if user.username else ''}\n"
        f"💰 مبلغ: <b>{transaction.amount:,}</b> تومان\n"
        f"💠 ارز: {coin.label} ({coin.network})\n"
        f"🔗 TXID: <code>{txid}</code>\n"
        f"🧾 فاکتور: <code>{transaction.id}</code>"
    )
    for uid in config.SUPER_USERS:
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


async def apply_offline_review(cp, action: str, bot) -> str:
    """Apply approve/reject to a pending offline payment — the SINGLE credit
    path, shared by the bot's inline review and the web→Redis queue. Idempotent
    (already-finished guard). Approve sets the tx ``finished`` (= credit) +
    activates/notifies; reject marks it ``rejected``. Returns:
    ``approved`` | ``rejected`` | ``already`` | ``notfound``."""
    if cp is None:
        return "notfound"
    transaction = cp.transaction
    if transaction.status == Transaction.Status.finished:
        return "already"

    if action == "approve":
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
        helpers.transaction_log(transaction=transaction, payment=cp)
        jobs.activate_service(transaction, msg)
        return "approved"

    async with in_transaction():
        transaction.status = Transaction.Status.rejected
        await transaction.save()
        cp.payment_status = CryptoPayment.PaymentStatus.failed
        await cp.save()
    try:
        await bot.send_message(
            transaction.user_id,
            f"❌ پرداختِ آفلاینِ شما (فاکتور <code>{transaction.id}</code>) رد شد.\n"
            "اگر مبلغی واریز کرده‌اید، با پشتیبانی تماس بگیرید.",
        )
    except Exception:  # noqa: BLE001
        pass
    return "rejected"


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
        await apply_offline_review(await _fetch_offline_cp(cp_id), action, bot)


@router.callback_query(OfflineReviewCb.filter(), IsSuperUser())
async def offline_review(
    qmsg: CallbackQuery, user: User, callback_data: OfflineReviewCb
):
    cp = await _fetch_offline_cp(callback_data.cp_id)
    result = await apply_offline_review(cp, callback_data.action, qmsg.bot)
    if result == "notfound":
        return await qmsg.answer("پرداخت یافت نشد!", show_alert=True)
    if result == "already":
        return await qmsg.answer("این پرداخت قبلاً تأیید شده است.", show_alert=True)
    if result == "approved":
        await qmsg.answer("تأیید شد ✅", show_alert=True)
        _suffix = f"\n\n✅ تأیید توسط <code>{user.id}</code>"
    else:
        await qmsg.answer("رد شد", show_alert=True)
        _suffix = f"\n\n❌ رد توسط <code>{user.id}</code>"

    # stamp the admin card + drop the buttons
    try:
        if qmsg.message.caption is not None:
            await qmsg.message.edit_caption(caption=(qmsg.message.caption or "") + _suffix)
        else:
            await qmsg.message.edit_text(text=(qmsg.message.text or "") + _suffix)
    except Exception:  # noqa: BLE001
        try:
            await qmsg.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
