from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from aiogram.exceptions import TelegramBadRequest

from app.jobs import logger
from app.main import bot, scheduler
from app.models.user import InvoiceReminder, User
from app.utils import settings


async def remind_invoices():
    _settings = settings.get_settings()
    if _settings.remind_invoices_each_n_days == 0:
        return

    await InvoiceReminder.filter(
        created_at__lt=dt.utcnow() - td(days=_settings.remind_invoices_each_n_days)
    ).delete()

    all_users = await User.filter(blocked_bot=False).all()
    for user in all_users:
        if await InvoiceReminder.filter(
            user_id=user.id,
        ).exists():
            continue
        balance = await user.get_balance()
        has_to_pay = balance * -1 if balance < 0 else 0
        if has_to_pay >= _settings.remind_invoices_after_amount:
            try:
                text = f"""
♻️ کاربر گرامی شما به مقدار <code>{has_to_pay:,}</code> تومان در ربات بدهکار هستید!

لطفا هرچه زودتر نسبت به شارژ حساب خود اقدام نمایید🙏
"""
                await bot.send_message(chat_id=user.id, text=text)
                await InvoiceReminder.create(user=user)
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc):
                    user.blocked_bot = True
                    await user.save(update_fields=["blocked_bot"])
                    continue
            except Exception as err:
                logger.error(err)


scheduler.add_job(
    remind_invoices,
    "interval",
    hours=7,
    id="remind_invoices",
    replace_existing=True,
    start_date=dt.now(UTC) + td(seconds=10),
)
