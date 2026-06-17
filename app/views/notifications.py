from datetime import datetime as dt
from datetime import timedelta as td

from aiohttp import web

from app.jobs.check_reserves import activate_reserve
from app.keyboards.user.proxy import ProxySettings
from app.main import bot, scheduler
from app.models.proxy import Proxy, Reserve
from app.utils.settings import get_settings
from marzban_client.models.user_response import UserResponse

from . import logger

routes = web.RouteTableDef()


def validated_webhook_secret(request: web.Request) -> bool:
    settings = get_settings()
    if not settings.marzban_webhook_secret:
        return True
    if request.headers.get("x-webhook-secret") is None:
        return False
    if request.headers.get("x-webhook-secret") == settings.marzban_webhook_secret:
        return True


@routes.post("/webhook/")
async def marzban_webhook_requests(request: web.Request):
    logger.info(f"Recieved webhook update: {request}")
    if not request.can_read_body:
        return web.Response(status=400)
    if not validated_webhook_secret(request):
        return web.Response(status=401)

    logger.debug(f"{request} body: {await request.text()}")

    notifications = await request.json()
    for notification in notifications:
        action = notification.get("action")
        username = notification.get("username")
        proxy = await Proxy.filter(username=username).first()
        if not proxy:
            logger.error(f"Proxy {username} not found to process the update!")
            continue
        text = f"""
🔔 اعلان جدید!

🖥 <code>{proxy.username}</code> {f'<b>({proxy.custom_name})</b>' if proxy.custom_name else ''}

"""

        if action == "user_limited":
            sv_proxy = UserResponse.from_dict(notification.get("user"))
            await Proxy.filter(id=proxy.id).update(status=sv_proxy.status)
            text += "🔒 اشتراک به دلیل اتمام حجم محدود شد!"
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
            if await Reserve.filter(proxy_id=proxy.id).exists():
                scheduler.add_job(
                    activate_reserve,
                    "date",
                    id=f"reserves:queue:{proxy.id}",
                    args=(proxy.id,),
                    run_date=dt.utcnow() + td(seconds=10),
                )
                await bot.send_message(
                    proxy.user_id,
                    text="✅ پلن پشتیبان شما تا لحظاتی دیگر فعال خواهد شد! لطفا کمی صبر کنید.",
                )

        elif action == "user_expired":
            sv_proxy = UserResponse.from_dict(notification.get("user"))
            await Proxy.filter(id=proxy.id).update(status=sv_proxy.status)
            text += "⏳ اشتراک به دلیل اتمام دوره منقضی شد!"
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
        elif action == "user_enabled":
            sv_proxy = UserResponse.from_dict(notification.get("user"))
            await Proxy.filter(id=proxy.id).update(status=sv_proxy.status)
            text += "✅ اشتراک فعال شد!"
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
        elif action == "user_disabled":
            sv_proxy = UserResponse.from_dict(notification.get("user"))
            await Proxy.filter(id=proxy.id).update(status=sv_proxy.status)
            text += "❌ اشتراک غیرفعال شد!"
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
        elif action == "user_deleted":
            await proxy.delete()
            text += "❌ اشتراک از سرور حذف شد!"
            await bot.send_message(
                proxy.user_id,
                text=text,
            )

        elif action == "reached_usage_percent":
            percent = notification.get("used_percent")
            text += f"""⚠️ شما {int(percent)} درصد از حجم اشتراک را مصرف کرده اید!
جهت قطع نشدن پروکسی نسبت به تمدید آن اقدام کنید.
"""
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )

        elif action == "reached_days_left":
            days = notification.get("days_left")
            text += f"""⚠️ فقط {days} روز تا اتمام اشتراک باقی مانده‌است!
جهت قطع نشدن پروکسی نسبت به تمدید آن اقدام کنید.
"""
            await bot.send_message(
                proxy.user_id,
                text=text,
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
    return web.Response(status=200)
