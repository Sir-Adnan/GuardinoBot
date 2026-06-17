from aiogram.types import Message

from app.handlers.user import proxy, purchase
from app.keyboards.user.proxy import ProxySettings, RenewMethods, RenewSelectMethod
from app.main import bot
from app.models.user import Invoice, Transaction
from app.utils.bg import bg_job


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
            text = f"""
✅ سرویس {draft_invoice.service.display_name} با موفقیت فعال شد!

💡 برای مدیریت اشتراک خریداری شده دکمه زیر را کلیک کنید👇
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
