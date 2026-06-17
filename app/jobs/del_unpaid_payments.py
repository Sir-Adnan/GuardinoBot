from datetime import datetime as dt
from datetime import timedelta as td

from tortoise.expressions import Q

from app.jobs import logger
from app.main import scheduler
from app.models.user import Invoice, Transaction


async def delete_unpaid_payments():
    unpaid_transactions = Transaction.filter(
        ~Q(status=Transaction.Status.finished | Transaction.Status.partially_paid),
        created_at__lt=dt.now() - td(days=14),
    )
    draft_invoices = Invoice.filter(
        is_paid=False,
        is_draft=True,
        created_at__lt=dt.now() - td(days=14),
    )
    if (count := await unpaid_transactions.count()) > 0:
        logger.info(f"Deleting {count} unpaid transactions...")
        await unpaid_transactions.delete()
    if (count := await draft_invoices.count()) > 0:
        logger.info(f"Deleting {count} draft invoices...")
        await draft_invoices.delete()


scheduler.add_job(
    delete_unpaid_payments,
    "interval",
    hours=24,
    id="delete_unpaid_payments",
    replace_existing=True,
    start_date=dt.now() + td(seconds=10),
)
