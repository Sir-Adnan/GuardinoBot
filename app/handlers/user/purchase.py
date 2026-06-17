from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td

from aiogram import F
from aiogram.types import CallbackQuery, Message
from jdatetime import datetime as jdt
from jdatetime import timedelta as jtd
from tortoise.expressions import F as TF
from tortoise.expressions import Q, RawSQL
from tortoise.transactions import in_transaction

from app.handlers.start import main_menu_handler
from app.keyboards.base import MainMenu
from app.keyboards.user.proxy import Proxies, ProxiesActions
from app.keyboards.user.purchase import PurchaseService, Services, ServicesActions
from app.main import bot, redis
from app.marzban import Marzban
from app.models.proxy import Proxy
from app.models.server import Server
from app.models.service import Service, ServiceMenu
from app.models.user import GiftPayment, Invoice, Transaction, User
from app.utils import helpers, settings, texts
from app.utils.filters import IsJoinedToChannel, IsTestServiceName
from app.utils.misc import RTL
from app.utils.rate_limit import RateLimit, is_locked, lock
from marzban_client.api.user import add_user
from marzban_client.models.user_create import UserCreate
from marzban_client.models.user_create_inbounds import UserCreateInbounds
from marzban_client.models.user_create_proxies import UserCreateProxies
from marzban_client.models.user_response import UserResponse
from marzban_client.models.user_status import UserStatus

from . import router
from .proxy import show_proxy


async def can_get_test_service(
    user: User, service: Service, qmsg: CallbackQuery | Message
) -> bool:
    _settings = settings.get_settings()
    if user.role == User.Role.user:
        if await user.purchased_services.filter(id=service.id).exists():
            if isinstance(qmsg, CallbackQuery):
                await qmsg.answer(
                    "❌ شما قبلا یک بار این سرویس را فعال کرده‌اید!", show_alert=True
                )
            else:
                await qmsg.answer("❌ شما قبلا یک بار این سرویس را فعال کرده‌اید!")
            return False
    elif user.role == User.Role.reseller:
        count = (
            await redis.get(
                f"service:{service.id}:purchased:daily:_{jdt.today().strftime(format='%Y%m%d')}:{user.id}"
            )
        ) or 0
        limit = (
            user.setting.daily_test_services
            if user.setting
            else _settings.default_daily_test_services
        )
        if count > limit:
            if isinstance(qmsg, CallbackQuery):
                await qmsg.answer(
                    f"❌ شما نمی‌توانید بیش از {limit} بار در روز این سرویس را فعال کنید!",
                    show_alert=True,
                )
            else:
                await qmsg.answer(
                    f"❌ شما نمی‌توانید بیش از {limit} بار در روز این سرویس را فعال کنید!"
                )
            return False
    return True


async def record_purchase_service(user: User, service: Service) -> None:
    await service.purchased_by.add(user)
    if user.Role == User.Role.reseller:
        today = jdt.today()
        await redis.incr(
            f"service:{service.id}:purchased:daily:_{today.strftime(format='%Y%m%d')}:{user.id}"
        )
        await redis.expireat(
            f"service:{service.id}:purchased:daily:{user.id}", today + jtd(days=1)
        )


@router.message(F.text == MainMenu.purchase, IsJoinedToChannel())
@router.callback_query(Services.Callback.filter(F.action == ServicesActions.show))
async def purchase(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: Services.Callback | None = None,
):
    if callback_data and callback_data.menu_id:
        menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
        has_prev = True
        sub_menues = ServiceMenu.filter(parent_id=callback_data.menu_id, purchase=True)
        services = menu.services.filter()
    else:
        menu = None
        has_prev = False
        sub_menues = ServiceMenu.filter(parent_id=None, purchase=True)
        # find services which dont belong to any menu
        services = Service.filter(
            Q(
                id__not_in=RawSQL("(SELECT `service_id` FROM `services_to_menues`)"),
            )
        )

    services = services.filter(server__is_enabled=True, purchaseable=True)

    if user.role == User.Role.user:
        services = services.filter(resellers_only=False)
        sub_menues = sub_menues.filter(resellers_only=False)
    elif user.role == User.Role.reseller:
        services = services.filter(users_only=False)
        sub_menues = sub_menues.filter(users_only=False)

    services = services.filter(
        Q(user_filter=False) | Q(user_filters__id=user.id)
    )  # filter service based on user_filter field

    if not await services.all().count() and not await sub_menues.all().count():
        text = "😢 در حال حاضر سرویسی برای خرید موجود نمی‌باشد!"
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text, show_alert=True)
        return await qmsg.answer(text)

    _texts = texts.get_texts()
    if not menu:
        text = _texts.purchase.value
    else:
        text = menu.description or _texts.purchase.value

    mns = [(sm.id, sm.title) for sm in await sub_menues.all()]
    svs = [
        (service.id, await service.get_display_name(user=user, type="purchase"))
        for service in await services.all()
    ]
    markup = Services(
        sub_menues=mns,
        services=svs,
        menu_id=menu.id if menu else 0,
        parent_menu_id=menu.parent_id if menu else 0,
        has_previous=has_prev,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    await qmsg.answer(text, reply_markup=markup)


@router.message(
    IsTestServiceName(),
    IsJoinedToChannel(),
)
@router.callback_query(
    Services.Callback.filter(F.action == ServicesActions.show_service)
)
async def show_service(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: Services.Callback = None,
    service_id: int = None,
):
    if service_id is None:
        service_id = callback_data.service_id
    menu_id = callback_data.menu_id if callback_data else 0
    q = Service.filter(server__is_enabled=True, purchaseable=True, id=service_id)

    if user.role == User.Role.user:
        q = q.filter(resellers_only=False)
    elif user.role == User.Role.reseller:
        q = q.filter(users_only=False)

    q = q.filter(
        Q(user_filter=False) | Q(user_filters__id=user.id)
    )  # filter service based on user_filter field

    service = await q.first()
    if not service:
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer("❌ سرویس مورد نظر یافت نشد!", show_alert=True)
            return await purchase(qmsg, user)
        await qmsg.answer("❌ سرویس مورد نظر یافت نشد!", show_alert=True)
        return main_menu_handler(qmsg, user)
    await user.fetch_related("setting")

    if service.is_test_service and not (
        await can_get_test_service(user, service, qmsg)
    ):
        return

    price = await service.get_price()
    text = f"""
💎 {service.name}
🕐 مدت زمان: {helpers.hr_time(service.expire_duration, lang="fa") if service.expire_duration else '♾'}
🖥 حجم: {helpers.hr_size(service.data_limit, lang="fa") if service.data_limit else '♾'}
💰 قیمت: {f'{price:,} تومان' if price else 'رایگان'}
{RTL}~~~~~~~~~~~~~~~~~~~~~~~~"""
    if not price:
        text += """
🛍 برای خرید و فعالسازی سرویس، دکمه زیر را کلیک کنید👇"""
        markup = PurchaseService(
            service.id,
            discount_id=None,
            menu_id=menu_id,
            back_callback=Services.Callback(
                menu_id=menu_id, action=ServicesActions.show
            ),
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=markup)
        return await qmsg.answer(text, reply_markup=markup)

    discount = None
    if user.setting and (discount_percentage := user.setting.discount_percentage):
        price = await service.get_price(discount_percent=discount_percentage)
        text += f"""
🔥 تخفیف ویژه شما: <code>{discount_percentage}</code> درصد
💰 قیمت با تخفیف: <b>{price:,}</b> تومان
{RTL}~~~~~~~~~~~~~~~~~~~~~~~~"""
    else:
        discount = await service.get_discount(user=user, type="purchase")
        if discount:
            price = await service.get_price(discount=discount)
            text += f"""
🎁 تخفیف: <b>{discount.percentage}</b> درصد {f'(<code>{discount.code}</code>)' if discount.code else ''}
💰 قیمت با تخفیف: <b>{price:,}</b> تومان
{RTL}~~~~~~~~~~~~~~~~~~~~~~~~"""

    balance = await user.get_available_credit()
    text += f"""
🏦 اعتبار حساب شما: <b>{balance:,}</b> تومان
"""
    if balance >= price:
        text += f"""{RTL}~~~~~~~~~~~~~~~~~~~~~~~~
🛍 برای خرید و فعالسازی سرویس، دکمه زیر را کلیک کنید👇"""
        markup = PurchaseService(
            service.id,
            discount_id=discount.id if discount is not None else None,
            menu_id=menu_id,
            back_callback=Services.Callback(
                menu_id=menu_id, action=ServicesActions.show
            ),
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=markup)
        return await qmsg.answer(text, reply_markup=markup)

    if balance > 0:
        text += f"""💵 مبلغ قابل پرداخت از اعتبار: <b>{balance if balance > 0 else 0:,}</b> تومان
        """
    text += f"""{RTL}~~~~~~~~~~~~~~~~~~~~~~~~
    """
    text += "موجودی حساب شما برای فعالسازی این سرویس کافی نیست! برای پرداخت مستقیم دکمه زیر را کلیک کنید👇"
    markup = PurchaseService(
        service.id,
        has_balance=False,
        pay_amount=price - balance,
        discount_id=discount.id if discount is not None else None,
        menu_id=menu_id,
        back_callback=Services.Callback(menu_id=menu_id, action=ServicesActions.show),
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


class ServerError(Exception):
    pass


class PurchaseError(Exception):
    pass


async def activate_service(
    service: Service,
    user: User,
    discount_id: int = None,
    invoice_id: int = None,
) -> Proxy:
    await user.fetch_related("setting")
    discount = None
    if user.setting and user.setting.discount_percentage:
        price = await service.get_price(
            discount_percent=user.setting.discount_percentage,
        )
    else:
        discount = await service.get_discount(user=user, type="purchase")
        price = await service.get_price(discount=discount)
    _settings = settings.get_settings()

    if is_locked(user_id=user.id):
        raise PurchaseError(
            "تعداد درخواست‌های شما زیاد است! لطفا کمی بعد دوباره تلاش کنید."
        )

    if discount_id and (discount is None or discount.id != discount_id):
        raise PurchaseError(
            "❌ کد تخفیف اعمال شده شما منقضی شده است! لطفا دوباره تلاش کنید."
        )

    async def create_user_on_server(max_retry: int = 1, tries: int = 0) -> UserResponse:
        client = Marzban.get_server(service.server_id)
        inbounds = await service.get_inbounds()
        user_inbounds = UserCreateInbounds.from_dict(inbounds)
        user_proxies = UserCreateProxies.from_dict(
            {
                protocol: service.create_proxy_protocols(protocol)
                for protocol in inbounds
            }
        )
        await user.fetch_related("setting")
        proxy_obj = UserCreate(
            username=await helpers.generate_proxy_username(
                user, server_id=service.server_id, _settings=_settings
            ),
            proxies=user_proxies,
            inbounds=user_inbounds,
            data_limit=service.data_limit,
            data_limit_reset_strategy=service.usage_reset_strategy
            if service.data_limit
            else service.UsageResetStrategy.no_reset,
        )
        if service.create_on_hold_users:
            proxy_obj.status = UserStatus.ON_HOLD
            proxy_obj.on_hold_expire_duration = (
                service.expire_duration if service.expire_duration else None
            )
            proxy_obj.on_hold_timeout = dt.now(UTC) + td(
                seconds=_settings.on_hold_timeout_seconds
            )
        else:
            proxy_obj.expire = (
                helpers.get_expire_timestamp(service.expire_duration)
                if service.expire_duration
                else None
            )

        resp = await add_user.asyncio_detailed(client=client, body=proxy_obj)
        if resp.status_code == 409:  # conflict Error
            # try to increment total_proxies of the server by 1 and try again
            if tries < max_retry:
                await Server.filter(id=service.server_id).update(
                    total_proxies=TF("total_proxies") + 1
                )
                return await create_user_on_server(tries=tries + 1, max_retry=max_retry)
            raise ServerError(
                "Could not create user most probably due to Conflict Error"
            )
        return resp.parsed

    with lock(user_id=user.id):
        async with in_transaction():
            balance = await user.get_available_credit()
            if balance < price:
                raise PurchaseError(
                    "⁉️ اعتبار حساب شما برای فعالسازی این سرویس کافی نیست!"
                )

            sv_proxy = await create_user_on_server(max_retry=5)

            proxy = await Proxy.create(
                username=sv_proxy.username,
                service_id=service.id,
                user_id=user.id,
                cost=price,
                server_id=service.server_id,
            )
            if (
                invoice_id
                and (
                    invoice := await Invoice.filter(
                        id=invoice_id, is_draft=True
                    ).first()
                )
                is not None
            ):
                invoice.is_draft = False
                invoice.is_paid = True
                invoice.proxy_id = proxy.id
                invoice.amount = price
                await invoice.save(
                    update_fields=["is_draft", "is_paid", "proxy_id", "amount"]
                )
            else:
                invoice = await Invoice.create(
                    amount=price,
                    type=Invoice.Type.purchase,
                    is_paid=not user.is_postpaid,
                    service=service,
                    proxy=proxy,
                    user=user,
                )
            if discount:
                discount.used_times = TF("used_times") + 1
                await discount.save(update_fields=["used_times"])
                await discount.used_by.add(user)
            if not user.gift_given_to_referrer and user.referrer_id:
                gift_trx = await Transaction.create(
                    type=Transaction.PaymentType.gift,
                    status=Transaction.Status.finished,
                    amount=invoice.amount * _settings.referral_discount_percent / 100,
                    user_id=user.referrer_id,
                )
                await GiftPayment.create(
                    type=GiftPayment.GiftType.referral,
                    invitee=user,
                    transaction=gift_trx,
                )
                user.gift_given_to_referrer = True
                await user.save()
                try:
                    await bot.send_message(
                        user.referrer_id,
                        f"🎉 تبریک! شما مبلغ {gift_trx.amount:,} تومان به عنوان هدیه دعوت از دیگران دریافت کردید.",
                    )
                except Exception:
                    pass
        await record_purchase_service(user, service)
        helpers.order_log(
            proxy=proxy, type="new", service=service, user=user, amount_paid=price
        )
        return proxy


@router.callback_query(PurchaseService.Callback.filter())
async def purchase_service(
    query: CallbackQuery, user: User, callback_data: PurchaseService.Callback
):
    if await RateLimit.throttled(query, user.id, "purchase", count=1, duration=8):
        return

    q = Service.filter(
        server__is_enabled=True, purchaseable=True, id=callback_data.service_id
    )
    if user.role == User.Role.user:
        q = q.filter(resellers_only=False)
    elif user.role == User.Role.reseller:
        q = q.filter(users_only=False)

    service = await q.first()

    if not service:
        await query.answer("❌ سرویس مورد نظر یافت نشد!", show_alert=True)
        return await purchase(query, user)

    await user.fetch_related("setting")
    if service.is_test_service and not (
        await can_get_test_service(user, service, query)
    ):
        return

    try:
        proxy = await activate_service(
            service=service, user=user, discount_id=callback_data.discount_id
        )
        await query.answer(
            "✅ اشتراک مورد نظر برای شما فعال شد!",
            show_alert=True,
        )
        return await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id, action=ProxiesActions.show_proxy
            ),
        )
    except PurchaseError as err:
        return await query.answer(text=str(err), show_alert=True)
    except Exception as err:
        await query.answer(
            "❌ خطایی در خرید سرویس رخ داد! لطفا بعدا دوباره تلاش کنید.",
            show_alert=True,
        )
        raise err
