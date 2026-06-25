from aiogram.types import Message
from tortoise.transactions import in_transaction

from app.handlers.user import proxy, purchase
from app.keyboards.user.proxy import ProxySettings, RenewMethods, RenewSelectMethod
from app.logger import get_logger
from app.main import bot
from app.models.proxy import Proxy
from app.models.user import Invoice, Transaction
from app.panels import get_panel
from app.utils.bg import bg_job

logger = get_logger("plugins/payment/jobs")


async def _subscription_links_text(dbproxy: Proxy) -> str:
    """All subscription/config links for a freshly activated proxy, ready to
    paste into the activation message. For Guardino this returns the master
    (default) sub link *and* every per-node link; for Marzban/PasarGuard the
    sub link + config links. Best-effort: returns '' if the panel is
    unreachable, so a links hiccup never blocks activation."""
    try:
        sv_proxy = await get_panel(dbproxy.server_id).get_user(dbproxy.username)
    except Exception:  # noqa: BLE001 - never block activation on a links fetch
        logger.warning(
            "activation links fetch failed for %s", dbproxy.username, exc_info=True
        )
        return ""
    if not sv_proxy:
        return ""
    parts: list[str] = []
    if sv_proxy.subscription_url:
        parts.append(
            f"🔗 لینک اشتراک (Sub):\n<code>{sv_proxy.subscription_url}</code>"
        )
    if sv_proxy.links:
        cfgs = "\n\n".join(f"<code>{link}</code>" for link in sv_proxy.links)
        parts.append(f"🔗 لینک‌های اتصال:\n{cfgs}")
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\n"


@bg_job
async def activate_service(transaction: Transaction, message: Message) -> None:
    try:
        draft_invoice = (
            await Invoice.filter(transaction_id=transaction.id, is_draft=True)
            .first()
            .prefetch_related("service", "proxy")
        )
        if not draft_invoice:
            return
        await transaction.fetch_related("user")
        if draft_invoice.type == Invoice.Type.purchase:
            dbproxy = await purchase.activate_service(
                service=draft_invoice.service,
                user=transaction.user,
                invoice_id=draft_invoice.id,
            )
            links_section = await _subscription_links_text(dbproxy)
            text = f"""
✅ سرویس {draft_invoice.service.display_name} با موفقیت فعال شد!

{links_section}💡 برای مدیریت اشتراک خریداری شده دکمه زیر را کلیک کنید👇
"""
            markup = ProxySettings(proxy=dbproxy).as_markup()
            await bot.send_message(transaction.user_id, text=text, reply_markup=markup)
        elif draft_invoice.type == Invoice.Type.renew_now:
            await proxy.renew_proxy_now(
                message,
                transaction.user,
                callback_data=RenewSelectMethod.Callback(
                    proxy_id=draft_invoice.proxy.id,
                    service_id=draft_invoice.service.id,
                    method=RenewMethods.now,
                    confirmed=True,
                ),
                invoice_id=draft_invoice.id,
            )
        elif draft_invoice.type == Invoice.Type.renew_reserve:
            await proxy.renew_proxy_reserve(
                message,
                transaction.user,
                callback_data=RenewSelectMethod.Callback(
                    proxy_id=draft_invoice.proxy.id,
                    service_id=draft_invoice.service.id,
                    method=RenewMethods.reserve,
                    confirmed=True,
                ),
                invoice_id=draft_invoice.id,
            )
        else:
            return
    except purchase.PurchaseError as err:
        await bot.send_message(
            transaction.user_id,
            f"خطایی در فعالسازی سرویس {draft_invoice.service.display_name} رخ داد: {err}",
        )


async def _remove_proxy_from_panel(dbproxy: Proxy) -> bool:
    """Best-effort removal of a proxy from its panel. Returns False (and logs)
    on any failure so the caller can still fix the balance and warn the admin
    to remove it manually."""
    try:
        panel = get_panel(dbproxy.server_id)
        if await panel.get_user(dbproxy.username) is not None:
            await panel.remove_user(dbproxy.username)
        return True
    except Exception:  # noqa: BLE001 - balance fix must proceed regardless
        logger.warning(
            "revoke: panel removal failed for %s", dbproxy.username, exc_info=True
        )
        return False


async def revoke_activated_transaction(transaction: Transaction) -> str:
    """Inverse of :func:`activate_service`. When an already-accepted payment is
    rejected (fake/wrong receipt), undo the activation so the customer can't
    keep a free subscription and the balance can't go negative.

    Always sets the transaction to ``rejected`` (which removes the credited
    amount). For each *non-draft* invoice tied to the transaction:
      * purchase → remove the subscription (panel + bot) and delete the invoice,
        so the −price no longer counts and the balance nets back to ~0.
      * renew_*  → void the invoice only; the time/traffic extension cannot be
        rolled back automatically, so the admin is told to handle it manually.

    Draft (not-yet-activated) invoices and plain wallet top-ups have nothing to
    undo — the status flip alone reverses the credit. Idempotent. Returns a
    short Persian summary for the admin (esp. panel-removal failures / renew
    flags). Referral gift transactions are not auto-reversed (rare; flagged)."""
    notes: list[str] = []
    invoices = (
        await Invoice.filter(transaction_id=transaction.id, is_draft=False)
        .prefetch_related("proxy")
        .all()
    )
    for inv in invoices:
        dbproxy = inv.proxy
        if inv.type == Invoice.Type.purchase and dbproxy is not None:
            removed = await _remove_proxy_from_panel(dbproxy)
            async with in_transaction():
                await inv.delete()
                await dbproxy.delete()
            notes.append(
                f"اشتراک <code>{dbproxy.username}</code> حذف شد"
                if removed
                else f"⚠️ اشتراک <code>{dbproxy.username}</code> از ربات حذف شد "
                "ولی از پنل حذف نشد؛ لطفاً دستی حذف کنید"
            )
        elif inv.type in (Invoice.Type.renew_now, Invoice.Type.renew_reserve):
            uname = f" <code>{dbproxy.username}</code>" if dbproxy else ""
            await inv.delete()
            notes.append(
                f"⚠️ فاکتور تمدید باطل شد؛ تمدیدِ اشتراک{uname} به‌صورت خودکار "
                "برنمی‌گردد — لطفاً دستی اصلاح کنید"
            )
        else:
            await inv.delete()
            notes.append("فاکتور باطل شد")

    if transaction.status != Transaction.Status.rejected:
        transaction.status = Transaction.Status.rejected
        await transaction.save(update_fields=["status"])

    return "\n".join(notes) if notes else "موجودی اصلاح شد."
