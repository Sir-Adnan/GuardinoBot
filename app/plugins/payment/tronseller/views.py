from datetime import datetime as dt

from aiohttp import web

from app.logger import get_logger
from app.main import bot
from app.models.user import Transaction, TronsellerPayment
from app.plugins.payment import jobs
from app.utils import helpers, settings

from .clients import TronadoAPI, TronsellerError, TSWebhookResult

logger = get_logger("plugins/payment/tronseller")

routes = web.RouteTableDef()


def get_menu_title(
    provider: TronsellerPayment.Provider, _settings: "settings.Settings"
) -> str:
    if provider == TronsellerPayment.Provider.tronado:
        return _settings.payment_tronado.menu_title
    return "-"


@routes.post("/tronseller")
@routes.post("/tronseller/")
async def verify_payment(request: web.Request):
    _settings = settings.get_settings()
    if not request.can_read_body:
        return
    data = await request.json()
    logger.info(f"got ipn from tronseller: {data}")
    result = TSWebhookResult.model_validate(data)

    transaction = (
        await Transaction.filter(id=result.PaymentID)
        .prefetch_related("tronseller_payment")
        .first()
    )
    if not transaction:
        logger.debug(f"Processing payment {result.PaymentID}: payment not found")
        return web.json_response(
            {"status": False, "message": "Payment not found"}, status=404
        )

    if transaction.status == Transaction.Status.finished:
        logger.debug(
            f"Processing payment {result.PaymentID}: payment already processed"
        )
        return web.json_response(
            {"status": True, "message": "Payment already accepted"}
        )

    try:
        result = await TronadoAPI.get_order_by_payment_id(payment_id=transaction.id)
    except TronsellerError as err:
        logger.error(err)
        return web.json_response(
            {"status": False, "message": "Failed to verify payment"}, status=404
        )

    if result.IsPaid:
        logger.debug(f"Processing payment {result.PaymentID}: accepting payment")
        _settings = settings.get_settings()
        await transaction.update_from_dict(
            {
                "status": Transaction.Status.finished,
                "finished_at": dt.now(),
                "amount_paid": transaction.tronseller_payment.trx_rate
                * result.TronAmount,
            }
        ).save()
        await transaction.refresh_from_db()
        transaction.tronseller_payment.extra_data = result.model_dump_json()
        await transaction.tronseller_payment.save()
        await transaction.tronseller_payment.refresh_from_db()

        gateway_title = get_menu_title(
            provider=transaction.tronseller_payment.provider, _settings=_settings
        )
        text = f"""
✅ پرداخت شما از طریق {gateway_title} با موفقیت تأیید شد و مبلغ <b>{transaction.amount:,}</b> تومان به حساب شما اضافه شد!

💳 شماره فاکتور: <b>{transaction.id}</b>
💴 مبلغ پرداختی: <b>{transaction.amount_paid:,}</b> تومان
‌‌
"""
        msg = await bot.send_message(transaction.user_id, text)
        await transaction.fetch_related("tronseller_payment")
        helpers.transaction_log(
            transaction=transaction, payment=transaction.tronseller_payment
        )
        jobs.activate_service(transaction, msg)
        return web.json_response(
            {"status": True, "message": "Payment accepted"}, status=200
        )

    return web.json_response(
        {"status": False, "message": "Payment not finished"}, status=400
    )
