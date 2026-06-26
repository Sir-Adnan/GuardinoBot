import io
from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td
from html import escape

import anyio
from aiogram import F, exceptions
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)
from apscheduler.jobstores.redis import JobLookupError
from tortoise.expressions import F as TF
from tortoise.expressions import Q, RawSQL
from tortoise.transactions import in_transaction

from app.jobs.check_reserves import activate_reserve
from app.keyboards.base import CancelUserForm, MainMenu
from app.keyboards.user.account import UserPanel, UserPanelAction
from app.keyboards.user.proxy import (
    FILTER_PROXY,
    SORT_PROXY,
    ConfirmProxyPanel,
    ConfirmRenew,
    Proxies,
    ProxiesActions,
    ProxyLinks,
    ProxyPanel,
    ProxyPanelActions,
    ProxySettings,
    RenewActions,
    RenewMethods,
    RenewSelectMethod,
    RenewSelectService,
    ReservePanel,
    ReservePanelAction,
    ResetPassword,
)
from app.main import redis, scheduler
from app.marzban import Marzban, ServerAuthenticationError
from app.models.proxy import Proxy, ProxyStatus, Reserve
from app.models.service import Service, ServiceMenu
from app.models.user import Invoice, User, UserSetting
from app.utils import helpers, qr, settings, texts
from app.utils.bg import bg_job
from app.utils.filters import IsJoinedToChannel, IsSubscriptionURL, IsSuperUser
from app.utils.rate_limit import RateLimit, is_locked, lock
from app.panels import ModifyUserParams, PanelError, PanelUserStatus, get_panel
from marzban_client.api.subscription import user_subscription_info

from . import logger, router

PROXY_STATUS = {
    PanelUserStatus.active: "فعال ✅",
    PanelUserStatus.disabled: "غیرفعال ❌",
    PanelUserStatus.limited: "محدود شده 🔒",
    PanelUserStatus.expired: "منقضی شده ⏳",
    PanelUserStatus.on_hold: "در انتظار اولین اتصال ⏸",
}

USAGE_RESET_STRATEGY = {
    "no_reset": "غیرفعال",
    "day": "روزانه",
    "week": "هفتگی",
    "month": "ماهانه",
    "year": "سالانه",
}


class SetCustomNameForm(StatesGroup):
    proxy_id = State()
    user_id = State()
    current_page = State()
    name = State()


class SearchProxiesForm(StatesGroup):
    user_id = State()
    parent_id = State()
    search_text = State()


class ApiUserError(Exception):
    pass


@router.message(F.text == MainMenu.proxies, IsJoinedToChannel())
@router.message(F.text.casefold() == MainMenu.cancel, StateFilter(SearchProxiesForm))
@router.callback_query(UserPanel.Callback.filter(F.action == UserPanelAction.proxies))
@router.callback_query(Proxies.Callback.filter(F.action == ProxiesActions.show))
async def proxies(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: Proxies.Callback | UserPanel.Callback = None,
    search_text: str = None,
):
    if isinstance(callback_data, Proxies.Callback):
        user_id = (
            callback_data.user_id
            if callback_data and callback_data.user_id
            else user.id
        )
        parent_id = (
            callback_data.parent_id
            if callback_data and callback_data.parent_id
            else None
        )
        page = callback_data.current_page if callback_data else 0
        search_text = callback_data.search_text
    else:
        user_id = user.id
        parent_id = None
        page = 0
        search_text = None

    if (user.role < user.Role.admin) and (user_id != user.id):
        return
    q = Proxy.filter(user_id=user_id)
    if (user.role == user.Role.admin) and (
        user_id != user.id
    ):  # admin can only see their childs proxies and themselves
        q = q.filter(user__parent_id=user.id)

    await user.fetch_related("setting")
    filter_by = (
        user.setting.proxy_list_filter_by.value
        if (user.setting and user.setting.proxy_list_filter_by)
        else "all"
    )
    if search_text:
        q = q.filter(
            Q(username__icontains=search_text) | Q(custom_name__icontains=search_text)
        )
    if filter_by and filter_by != "all":
        q = q.filter(status=filter_by)
    total_count = await q.count()
    q = q.limit(11).offset(0 if page == 0 else page * 10)
    count = await q.count()
    if total_count < 1 and filter_by == "all" and (search_text is None):
        text = "در حال حاضر هیچ پروکسی فعالی ندارید😬"
        if isinstance(qmsg, CallbackQuery):
            return qmsg.answer(text, show_alert=True)
        return qmsg.answer(text)

    sort_by = (
        user.setting.proxy_list_sort_by.value
        if (user.setting and user.setting.proxy_list_sort_by)
        else "-created_at"
    )
    if sort_by:
        q = q.order_by(sort_by)
    proxies = await q.prefetch_related("service").all()
    reply_markup = Proxies(
        proxies[:10],
        user_id=user_id,
        parent_id=parent_id,
        current_page=page,
        count=total_count,
        sort_by=sort_by,
        filter_by=filter_by,
        next_page=True if count > 10 else False,
        prev_page=True if page > 0 else False,
        search_text=search_text,
        back_to_user_info=True
        if user_id != user.id and user.role == User.Role.super_user
        else False,
    ).as_markup()
    start = 1 if page == 0 else (page * 10 + 1)
    end = 10 if page == 0 else ((start - 1) + (10 if count > 10 else count))
    text = f"""
🔵 لیست اشتراک‌های خریداری شده👇 (برای مدیریت هر اشتراک روی آن کلیک کنید)

🚦مشاهده: <b>{start}</b> تا <b>{end}</b> از <b>{total_count}</b>
    """
    if user_id != user.id:
        text += f"""
⚠️ ادمین عزیز شما در حال مشاهده لیست اشتراک‌های کاربر <code>{user_id}</code> هستید!
"""
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text,
                reply_markup=reply_markup,
            )
        return await qmsg.answer(
            text,
            reply_markup=reply_markup,
        )
    except exceptions.TelegramBadRequest:
        pass


@bg_job
async def refresh_proxies_job(query: CallbackQuery, user: User, user_id: int):
    await redis.set(f"proxies_refresh:ongoing:{user_id}", 1, 600)
    proxies = await Proxy.filter(user_id=user_id).all()

    for proxy in proxies:
        try:
            sv_proxy = await get_panel(proxy.server_id).get_user(proxy.username)
        except Exception as exc:
            await Proxy.filter(id=proxy.id).update(status=ProxyStatus.disabled)
            logger.error(f"Failed to update proxy {proxy.id}: {exc}")
            continue

        if sv_proxy is None:
            await proxy.delete()
            continue

        if proxy.status.value != sv_proxy.status.value:
            await Proxy.filter(id=proxy.id).update(
                status=ProxyStatus(sv_proxy.status.value)
            )

    await redis.delete(f"proxies_refresh:ongoing:{user_id}")
    await redis.set(f"can_refresh:{user_id}", 0, ex=86400)
    await query.message.answer("♻️ به روز رسانی اشتراک‌های شما با موفقیت به پایان رسید!")


@router.callback_query(
    Proxies.Callback.filter(F.action == ProxiesActions.refresh),
)
async def refresh_proxies(
    query: CallbackQuery, user: User, callback_data: Proxies.Callback
):
    user_id = callback_data.user_id or user.id
    if await redis.exists(f"proxies_refresh:ongoing:{user_id}"):
        return await query.answer(
            "♻️ بروزرسانی اشتراک‌های شما در حال انجام است... پس از بروزرسانی به شما اطلاع داده می‌شود.",
            show_alert=True,
        )

    if user.role < User.Role.admin:
        if await redis.exists(f"can_refresh:{user_id}"):
            return await query.answer(
                "❌ شما به تازگی لیست اشتراک‌های خود را به‌روزرسانی کرده‌اید. هر ۲۴ ساعت فقط ۱ بار امکان بروزرسانی وجود دارد!",
                show_alert=True,
            )

    await query.answer(
        "✅ به روز رسانی لیست پروکسی‌های شما در حال انجام است. پس از بروزرسانی به شما اطلاع داده می‌شود...",
        show_alert=True,
    )
    refresh_proxies_job(query, user, user_id)


@router.callback_query(
    Proxies.Callback.filter(F.action == ProxiesActions.cycle_sort),
)
async def proxy_cycle_sort(
    query: CallbackQuery, user: User, callback_data: Proxies.Callback
):
    await user.fetch_related("setting")
    if user.setting is None:
        user.setting = await UserSetting.create(
            user=user,
        )

    try:
        s = iter(UserSetting.SortProxyList)
        while next(s) != user.setting.proxy_list_sort_by:
            pass
        proxy_list_sort_by = next(s)
    except StopIteration:
        proxy_list_sort_by = next(
            iter(UserSetting.SortProxyList)
        )  # get first enum value

    q = UserSetting.filter(user_id=user.id)
    if not await q.first():
        await UserSetting.create(user_id=user.id, proxy_list_sort_by=proxy_list_sort_by)
    else:
        await q.update(proxy_list_sort_by=proxy_list_sort_by)

    await query.answer(
        f"✔️ ترتیب لیست: {SORT_PROXY.get(proxy_list_sort_by)}",
        show_alert=True,
    )
    await proxies(
        query,
        user,
        callback_data=Proxies.Callback(
            user_id=callback_data.user_id,
            action=ProxiesActions.show,
            current_page=callback_data.current_page,
            search_text=callback_data.search_text,
        ),
    )


@router.callback_query(
    Proxies.Callback.filter(F.action == ProxiesActions.cycle_filter),
)
async def proxy_cycle_filter(
    query: CallbackQuery, user: User, callback_data: Proxies.Callback
):
    await user.fetch_related("setting")
    if user.setting is None:
        user.setting = await UserSetting.create(
            user=user,
        )

    try:
        s = iter(UserSetting.FilterProxyList)
        while next(s) != user.setting.proxy_list_filter_by:
            pass
        proxy_list_filter_by = next(s)
    except StopIteration:
        proxy_list_filter_by = next(
            iter(UserSetting.FilterProxyList)
        )  # get first enum value

    q = UserSetting.filter(user_id=user.id)
    if not await q.first():
        await UserSetting.create(
            user_id=user.id, proxy_list_filter_by=proxy_list_filter_by
        )
    else:
        await q.update(proxy_list_filter_by=proxy_list_filter_by)

    await query.answer(
        f"✔️ فیلتر نمایش: {FILTER_PROXY.get(proxy_list_filter_by)}",
        show_alert=True,
    )
    await proxies(
        query,
        user,
        callback_data=Proxies.Callback(
            user_id=callback_data.user_id,
            action=ProxiesActions.show,
            current_page=callback_data.current_page,
            search_text=callback_data.search_text,
        ),
    )


@router.callback_query(Proxies.Callback.filter(F.action == ProxiesActions.search))
async def search_proxy_list(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: Proxies.Callback,
):
    await state.set_state(SearchProxiesForm.search_text)
    await state.update_data(
        user_id=callback_data.user_id,
        parent_id=callback_data.parent_id,
    )
    await query.message.answer(
        "✍️ نام اشتراک یا نام دلخواهی که برای اشتراک تنظیم کرده‌اید را برای جستجو وارد کنید:",
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )
    try:
        await query.message.delete()
    except exceptions.TelegramBadRequest:
        pass


@router.message(
    SearchProxiesForm.search_text,
    ~CommandStart(),
    ~Command("menu"),
)
async def get_proxies_serach_text(message: Message, user: User, state: FSMContext):
    text = message.text.strip().replace("\n", " ")
    if len(text) > 64:
        return await message.answer(
            "❌ متن جستجو نمی‌تواند بیشتر از ۶۴ کاراکتر باشد! دوباره وارد کنید:",
            reply_markup=CancelUserForm(cancel=True).as_markup(
                one_time_keyboard=True, resize_keyboard=True
            ),
        )
    data = await state.get_data()
    await state.clear()
    await message.reply("🔎 در حال جستجو...", reply_markup=ReplyKeyboardRemove())
    await proxies(
        message,
        user,
        callback_data=Proxies.Callback(
            user_id=data.get("user_id"),
            action=ProxiesActions.show,
            parent_id=data.get("parent_id"),
            search_text=text,
        ),
    )


@router.message(Command("proxy"), IsSuperUser())
async def admin_find_proxy(message: Message, user: User, command: CommandObject):
    proxy = (
        await Proxy.filter(username__iexact=command.args)
        .first()
        .prefetch_related("user")
    )
    if not proxy:
        return await message.reply("جستجو نتیجه‌ای نداشت!")
    text = f"""
نام اشتراک: <code>{proxy.username}</code>

اطلاعات صاحب اشتراک:

شناسه کاربری: <code>{proxy.user.id}</code>
نام کاربری: {f'@{proxy.user.username}' if proxy.user.username else '➖'}

برای مدیریت و اطلاعات بیشتر از این کاربر دستور زیر را ارسال کنید:
<code>/info {proxy.user.id}</code>
"""
    await message.answer(
        text=text,
        reply_markup=ProxySettings(proxy=proxy, user_id=proxy.user.id).as_markup(),
    )


@router.message(F.text == MainMenu.cancel, StateFilter(SetCustomNameForm))
@router.callback_query(Proxies.Callback.filter(F.action == ProxiesActions.show_proxy))
async def show_proxy(
    qmsg: Message | CallbackQuery,
    user: User,
    callback_data: Proxies.Callback | None = None,
    state: FSMContext | None = None,
    command: CommandObject | None = None,
):
    if command:
        proxy_id, user_id, current_page = None, None, 0
        proxy = await Proxy.filter(username__iexact=command.args).first()
    else:
        proxy_id, user_id, current_page = None, None, None
        if (state is not None) and (await state.get_state() is not None):
            data = await state.get_data()
            proxy_id, user_id, current_page = data.values()
            text = "🌀 عملیات لغو شد!"
            await state.clear()
            if isinstance(qmsg, CallbackQuery):
                await qmsg.answer(text)
            else:
                await qmsg.answer(text=text, reply_markup=ReplyKeyboardRemove())
        if callback_data:
            proxy_id, user_id, current_page = (
                proxy_id or callback_data.proxy_id,
                user_id or callback_data.user_id,
                current_page or callback_data.current_page,
            )
        proxy = await Proxy.filter(id=proxy_id).first()

    if not proxy:
        return await qmsg.answer("❌ اشتراک مورد نظر یافت نشد!")

    if user_id:
        if (user.role < user.Role.admin) and (user.id != user_id):
            return
        elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
            await proxy.fetch_related("user")
            if proxy.user.parent_id != user.id:
                return
    await proxy.fetch_related("service")
    _settings = settings.get_settings()
    sv_proxy = None
    unavailable_code = None
    try:
        sv_proxy = await get_panel(proxy.server_id).get_user(proxy.username)
        if sv_proxy is None:
            unavailable_code = 404
    except PanelError as exc:
        if exc.status_code == 401:
            raise ServerAuthenticationError(server_id=proxy.server_id)
        if exc.status_code == 403:
            unavailable_code = 403
        else:
            await qmsg.answer(
                "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
            )
            raise
    except Exception as err:
        await qmsg.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err
    if unavailable_code is not None:
        proxy.status = ProxyStatus.disabled
        await proxy.save()
        await proxy.refresh_from_db()
        text = f"""
    ❌ امکان دریافت اطلاعات این اشتراک از سرور وجود ندارد! (<code>{unavailable_code}</code>)

    شناسه پروکسی: {proxy.id}
    نام تنظیم شده: {proxy.custom_name if proxy.custom_name else '-'}
    نام کاربری: <code>{proxy.username}</code>

    سرویس: {proxy.service.display_name if proxy.service_id else '-'}
            """
        reply_markup = ProxyPanel(
            proxy,
            _settings=_settings,
            user_id=user_id,
            current_page=current_page,
            show_reserve=False,
            can_delete=False,
            renewable=False,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=reply_markup)
        return await qmsg.answer(text, reply_markup=reply_markup)
    if proxy.status.value != sv_proxy.status.value:
        proxy.status = sv_proxy.status.value
        await proxy.save()
        await proxy.refresh_from_db()
    text = f"""
⭐️ شناسه: <code>{sv_proxy.username}</code> {f'({proxy.custom_name})' if proxy.custom_name else ''}
{f'📱 پلن فعال: <b>{proxy.service.display_name}</b>' if proxy.service_id else ''}
🌀 وضعیت: <b>{PROXY_STATUS.get(sv_proxy.status)}</b>
⏳ تاریخ انقضا: <b>{helpers.hr_date(sv_proxy.expire) if sv_proxy.expire else '♾'}</b> {f'<i>({helpers.hr_time(sv_proxy.expire - dt.now().timestamp(), lang="fa")})</i>' if sv_proxy.expire and sv_proxy.status != PanelUserStatus.expired else ''}
📊 حجم مصرف شده: <b>{helpers.hr_size(sv_proxy.used_traffic, lang='fa')}</b>
{f'🔋 حجم باقی‌مانده: <b>{helpers.hr_size(sv_proxy.data_limit - sv_proxy.used_traffic ,lang="fa")}</b>' if sv_proxy.data_limit else ''}

📊 حجم مصرفی تمام دوره‌ها: {helpers.hr_size(sv_proxy.lifetime_used_traffic, lang='fa')}

"""
    if sv_proxy.data_limit_reset_strategy != "no_reset":
        text += f"♻️ بازنشانی خودکار حجم: {USAGE_RESET_STRATEGY.get(sv_proxy.data_limit_reset_strategy)}\n\n"
    text += texts.Texts.format(
        texts.get_texts().proxy_help,
        SUBSCRIPTION_URL=sv_proxy.subscription_url,
        CONFIG_LINKS=sv_proxy.links,
        ACTIVE_INBOUNDS=[
            protocol for protocol in sv_proxy.inbounds
        ],
    )
    if sv_proxy.status == PanelUserStatus.active and _settings.reset_password_button:
        text += """

💡 برای قطع اتصال افراد متصل می‌توانید از دکمه «تغییر پسوورد» استفاده کنید!"""

    if sv_proxy.status in (PanelUserStatus.active, PanelUserStatus.on_hold):
        text += """

💡 برای دریافت لینک‌های اتصال و Qr Code میتوانید از دکمه زیر استفاده کنید👇
"""
    await proxy.fetch_related("reserve")
    reply_markup = ProxyPanel(
        proxy,
        _settings=_settings,
        user_id=user_id,
        current_page=current_page,
        show_reserve=True if proxy.reserve else False,
        can_delete=(
            True
            if (
                (user.role == User.Role.super_user)
                or (
                    _settings.cancel_payback_days
                    and (user.role > User.Role.user)
                    and (
                        (dt.now(UTC) - td(days=_settings.cancel_payback_days))
                        <= proxy.created_at
                    )
                )
            )
            and (proxy.service_id and not proxy.service.is_test_service)
            else False
        ),
        renewable=(
            False
            if (
                proxy.service_id
                and (
                    proxy.service.one_time_only
                    or proxy.service.is_test_service
                    or not proxy.service.renewable
                )
            )
            else True
        ),
        can_disable=True if user.role >= _settings.disable_users_role else False,
        can_enable=(
            True
            if (user.role >= _settings.disable_users_role)
            and (sv_proxy.status.value == ProxyStatus.disabled.value)
            else False
        ),
    ).as_markup()
    qr_code_options = await qr.subscription_link_preview(
        proxy.id, sv_proxy.username, sv_proxy.subscription_url
    )

    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(
            text, reply_markup=reply_markup, link_preview_options=qr_code_options
        )
    return await qmsg.answer(
        text, reply_markup=reply_markup, link_preview_options=qr_code_options
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.set_name)
)
async def set_proxy_name(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: ProxyPanel.Callback,
):
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if not proxy:
        return await query.answer("❌ اشتراک مورد نظر یافت نشد!")

    user_id = callback_data.user_id if callback_data.user_id else user.id
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    await state.set_state(SetCustomNameForm.name)
    await state.update_data(
        proxy_id=proxy.id,
        user_id=user_id,
        current_page=callback_data.current_page or 0,
    )
    await query.message.answer(
        "✍️ اسم دلخواه خود برای اشتراک مورد نظر را ارسال کنید:",
        reply_markup=CancelUserForm(cancel=True).as_markup(
            one_time_keyboard=True, resize_keyboard=True
        ),
    )
    try:
        await query.message.delete()
    except exceptions.TelegramBadRequest:
        pass


@router.message(
    SetCustomNameForm.name,
    ~CommandStart(),
    ~Command("menu"),
)
async def get_proxy_name(message: CallbackQuery, user: User, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id") if data.get("user_id") else user.id
    proxy = await Proxy.filter(id=data.get("proxy_id")).first()
    current_page = data.get("current_page", 0)
    if not proxy:
        await state.clear()
        return await message.answer("❌ اشتراک مورد نظر یافت نشد!")

    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if len(message.text) > 64:
        return await message.answer("🚫 طول اسم باید کمتر از 64 کاراکتر باشد!")

    proxy.custom_name = message.text.replace("\n", " ")
    await proxy.save()
    await show_proxy(
        message,
        user,
        callback_data=Proxies.Callback(
            proxy_id=proxy.id,
            user_id=user_id,
            action=ProxiesActions.show_proxy,
            current_page=current_page,
        ),
    )
    await message.answer(
        "✅ اسم دلخواه برای پروکسی تنظیم شد!", reply_markup=ReplyKeyboardRemove()
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.disable)
)
async def disable_proxy(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ مطمئن هستید که میخواهید اشتراک مورد نظر را به صورت موقت غیرفعال کنید؟ تمامی افراد متصل قطع خواهند شد!",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.disable,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
        if sv_proxy and sv_proxy.status.value != proxy.status.value:
            proxy.status = sv_proxy.status.value
            await proxy.save()
        if (sv_proxy is None) or (sv_proxy.status.value != ProxyStatus.active.value):
            return await query.answer(
                f"🚫 به دلیل «{PROXY_STATUS.get(sv_proxy.status) if sv_proxy else 'نامشخص'}» بودن اشتراک امکان غیرفعال سازی موقت وجود ندارد!",
                show_alert=True,
            )
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err

    try:
        sv_proxy = await panel.set_status(proxy.username, PanelUserStatus.disabled)

        await query.answer("✅ اشتراک به صورت موقت غیرفعال شد", show_alert=True)
        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.enable))
async def enable_proxy(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ مطمئن هستید که میخواهید اشتراک مورد نظر را فعال کنید؟ ",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.enable,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
        if sv_proxy and sv_proxy.status.value != proxy.status.value:
            proxy.status = sv_proxy.status.value
            await proxy.save()
        if (sv_proxy is None) or (sv_proxy.status.value != ProxyStatus.disabled.value):
            return await query.answer(
                f"🚫 به دلیل «{PROXY_STATUS.get(sv_proxy.status) if sv_proxy else 'نامشخص'}» بودن اشتراک امکان فعال سازی وجود ندارد!",
                show_alert=True,
            )
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err

    try:
        sv_proxy = await panel.set_status(proxy.username, PanelUserStatus.active)

        await query.answer("✅ اشتراک فعال شد", show_alert=True)
        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.remove))
async def remove_proxy(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ مطمئن هستید که میخواهید سرویس مورد نظر را از لیست پروکسی‌های خود حذف کنید؟ پس از حذف امکان تمدید وجود نخواهد داشت!",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.remove,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err

    try:
        if sv_proxy:
            await panel.remove_user(proxy.username)
        await proxy.delete()

        await query.answer("✅ اشتراک از لیست پروکسی‌های شما حذف شد", show_alert=True)
        await proxies(
            query,
            user,
            callback_data=Proxies.Callback(
                user_id=callback_data.user_id,
                action=ProxiesActions.show,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_password)
)
async def reset_password(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    text = """
💡 در این بخش می‌توانید  دسترسی افراد متصل را قطع کنید!

برای انجام این کار دو روش دارید:
1️⃣ تغییر پسوورد: فقط پسوورد کانفیگ‌ها عوض شده و کاربر با استفاده از لینک اتصال هوشمند می‌تواند دوباره متصل شود.
2️⃣ تغییر اتصال هوشمند: لینک اتصال هوشمند کاربر را تغییر می‌دهد و کاربر توانایی آپدیت و استفاده از لینک اتصال هوشمند قدیمی را نخواهد داشت.

اگه میخواید دسترسی کاربر رو به صورت کامل قطع کنید، باید از هر دو روش استفاده کنید🫡
"""
    await query.message.edit_text(
        text,
        reply_markup=ResetPassword(
            proxy_id=callback_data.proxy_id,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
        ).as_markup(),
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_uuid)
)
async def reset_uuid(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ مطمئن هستید که میخواهید پسوورد سرویس مورد نظر تغییر کند؟ تمام افراد متصل قطع خواهند شد!",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.reset_uuid,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err
    try:
        await proxy.fetch_related("service")
        sv_proxy = await panel.reset_proxy_credentials(proxy.username, proxy.service)

        await query.answer("✅ پسوورد پروکسی تغییر یافت", show_alert=True)

        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.reset_subscription)
)
async def reset_subscription(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    if not callback_data.confirmed:
        return await query.message.edit_text(
            "⚠️ مطمئن هستید که میخواهید لینک اتصال هوشمند سرویس مورد نظر تغییر کند؟ امکان استفاده از لینک اتصال هوشمند قدیمی وجود نخواهد داشت!",
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.reset_subscription,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err
    try:
        await panel.revoke_subscription(proxy.username)

        await query.answer("✅ لینک اتصال هوشمند تغییر یافت", show_alert=True)
        await qr.invalidate_qr_cache(proxy.id, proxy.username)
        await show_proxy(
            query,
            user,
            callback_data=Proxies.Callback(
                proxy_id=proxy.id,
                user_id=user_id,
                action=ProxiesActions.show_proxy,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.delete_wpayback)
)
async def delete_with_payback(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    _settings = settings.get_settings()
    if not callback_data.confirmed:
        text = """
⁉️ مطمئن هستید که میخواهید سرویس مورد نظر را حذف کنید؟ 

"""
        if _settings.cancel_payback_fee:
            text += f"مبلغ {_settings.cancel_payback_fee:,} تومان + میزان مصرف شده از سرویس از آن کم شده و باقیمانده به حساب شما برگشت داده می‌شود."
        else:
            text += "میزان مصرف شده از سرویس از مبلغ آن کم شده و باقیمانده به حساب شما برگشت داده می‌شود."
        text += """
⚠️  پس از حذف امکان تمدید وجود نخواهد داشت!
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmProxyPanel(
                action=ProxyPanelActions.delete_wpayback,
                proxy_id=callback_data.proxy_id,
                user_id=callback_data.user_id or user.id,
                current_page=callback_data.current_page,
            ).as_markup(),
        )

    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if not (
        (user.role == User.Role.super_user)
        or (
            _settings.cancel_payback_days
            and (user.role > User.Role.user)
            and (
                (dt.now(UTC) - td(days=_settings.cancel_payback_days))
                <= proxy.created_at
            )
        )
    ):
        return await query.answer(
            "❌ در حال حاضر امکان لغو و برگشت وجه سرویس وجود ندارد!"
        )

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید."
        )
        raise err

    try:
        async with in_transaction():
            await proxy.fetch_related("service")
            invoice = await Invoice.filter(proxy_id=proxy.id).first()
            amount = invoice.amount
            if proxy.service.data_limit:
                # calculate price per used bytes
                price_per_bytes = amount / proxy.service.data_limit
                invoice.amount = int(
                    _settings.cancel_payback_fee
                    + (sv_proxy.used_traffic * price_per_bytes)
                )

            elif proxy.service.expire_duration:
                # calculate price per used seconds
                price_per_seconds = amount / proxy.service.expire_duration
                started_at = sv_proxy.expire - proxy.service.expire_duration
                invoice.amount = _settings.cancel_payback_fee + (
                    (dt.now().timestamp() - started_at) * price_per_seconds
                )
            await invoice.save()
            if sv_proxy:
                await panel.remove_user(proxy.username)
            await proxy.delete()
            await invoice.refresh_from_db()

        await query.answer(
            f"✅ اشتراک با موفقیت حذف شد و مبلغ {amount - invoice.amount:,} تومان به حساب شما برگشت داده شد.",
            show_alert=True,
        )
        await proxies(
            query,
            user,
            callback_data=Proxies.Callback(
                user_id=callback_data.user_id,
                action=ProxiesActions.show,
                current_page=callback_data.current_page,
            ),
        )
    except Exception:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        )


async def _send_config_links(
    query: CallbackQuery,
    header: str,
    blocks: list[str],
    footer: str,
    markup,
) -> None:
    """Render config-link blocks across one or more messages, never splitting a
    single config across the Telegram 4096-char boundary. Header goes on the
    first message, footer + keyboard on the last. The first message edits the
    one the user tapped; the rest are sent as follow-ups."""
    sep = "\n\n"
    safe = 3500  # headroom under 4096 for header/footer + HTML entity expansion
    chunks: list[str] = []
    cur = ""
    for block in blocks:
        addition = (sep if cur else "") + block
        if cur and len(cur) + len(addition) > safe:
            chunks.append(cur)
            cur = block
        else:
            cur += addition
    if cur:
        chunks.append(cur)
    if not chunks:
        chunks = [""]

    last = len(chunks) - 1
    for i, chunk in enumerate(chunks):
        body = (header if i == 0 else "") + chunk + (footer if i == last else "")
        reply_markup = markup if i == last else None
        if i == 0:
            try:
                await query.message.edit_text(body, reply_markup=reply_markup)
                continue
            except exceptions.TelegramBadRequest:
                pass
        await query.message.answer(body, reply_markup=reply_markup)


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links))
async def proxy_links(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید.",
            show_alert=True,
        )
    try:
        config_links = await panel.get_config_links(sv_proxy)
    except Exception:  # noqa: BLE001 - degrade to whatever inline links exist
        config_links = list(sv_proxy.links or [])
    if not config_links:
        return await query.answer(
            "ℹ️ برای این سرویس لینک کانفیگ جداگانه‌ای موجود نیست؛ از «لینک اشتراک» (Sub) و Qr Code آن استفاده کنید.",
            show_alert=True,
        )

    protocols = sorted(
        {link.split("://", 1)[0].lower() for link in config_links if "://" in link}
    )
    header = (
        f"🔑 پروکسی‌های فعال: {', '.join(f'<b>{p.upper()}</b>' for p in protocols)}\n"
        "🔗 لینک‌های اتصال:\n\n"
    )
    footer = (
        "\n\n💡 برای کپی کردن هرکدام از لینک‌ها روی آن کلیک کنید👆\n\n"
        "💡 برای دریافت راهنمای اتصال و استفاده دستور /help را ارسال کنید!\n\n"
        "📷 برای دریافت <b>Qr code</b> از دکمه‌های زیر استفاده کنید👇"
    )
    blocks = [f"<code>{escape(link)}</code>" for link in config_links]
    markup = ProxyLinks(
        proxy=proxy, current_page=callback_data.current_page, user_id=user_id
    ).as_markup()
    await _send_config_links(query, header, blocks, footer, markup)


async def generate_qr_code(
    message: Message, links: list[str], username: str
) -> list[Message]:
    sent: list[Message] = []
    # Telegram media groups are capped at 10 items — batch so many configs
    # don't get rejected.
    for start in range(0, len(links), 10):
        photos = list()
        for link in links[start : start + 10]:
            f = io.BytesIO()
            _qr = qr.gen_qr(link)
            _qr.make_image().save(f)
            f.seek(0)
            photos.append(
                InputMediaPhoto(
                    media=BufferedInputFile(
                        f.getvalue(), filename=f"generated_qr_code_{username}"
                    ),
                    caption=f"{link.split('://')[0].upper()} ({username})",
                )
            )
        if photos:
            sent.extend(await message.answer_media_group(photos))
    return sent


async def generate_sub_qr_code(message: Message, link: str, username: str):
    f = io.BytesIO()
    _qr = qr.gen_qr(link)
    _qr.make_image().save(f)
    f.seek(0)
    await message.answer_photo(
        photo=BufferedInputFile(f.getvalue(), filename=f"generated_qr_code_{username}"),
        caption=f"⛓ لینک Qr code اتصال هوشمند ({username})",
    )


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links_allqr)
)
async def generate_qrcode_all(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید.",
            show_alert=True,
        )

    try:
        config_links = await panel.get_config_links(sv_proxy)
    except Exception:  # noqa: BLE001 - degrade to whatever inline links exist
        config_links = list(sv_proxy.links or [])
    if not config_links:
        return await query.answer(
            "ℹ️ لینک کانفیگ جداگانه‌ای برای این سرویس موجود نیست؛ از Qr Code «لینک اشتراک» استفاده کنید.",
            show_alert=True,
        )
    await query.answer("♻️ درحال ساخت و ارسال Qr code. چند لحظه منتظر بمانید...")
    await generate_qr_code(query.message, config_links, username=proxy.username)


@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.links_subqr)
)
async def generate_qrcode_sub(
    query: CallbackQuery, user: User, callback_data: ProxyPanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    try:
        panel = get_panel(proxy.server_id)
        sv_proxy = await panel.get_user(proxy.username)
    except Exception as err:
        await query.answer(
            "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید.",
            show_alert=True,
        )
        raise err
    if not sv_proxy:
        return await query.answer(
            "❌ خطایی در دریافت اطلاعات سرویس رخ داد! لطفا کمی بعد دوباره تلاش کنید.",
            show_alert=True,
        )

    await query.answer("♻️ درحال ساخت و ارسال Qr code. چند لحظه منتظر بمانید...")
    await generate_sub_qr_code(
        query.message, sv_proxy.subscription_url, username=proxy.username
    )


@router.callback_query(ProxyPanel.Callback.filter(F.action == ProxyPanelActions.renew))
@router.callback_query(
    RenewSelectService.Callback.filter(F.action == RenewActions.show)
)
async def renew_proxy(
    query: CallbackQuery,
    user: User,
    callback_data: ProxyPanel.Callback | RenewSelectService.Callback,
):
    if await Reserve.filter(proxy_id=callback_data.proxy_id).exists():
        return await query.answer(
            "⁉️ شما از قبل یک پلن پشتیبان برای این سرویس خریداری کرده‌اید و امکان تمدید وجود ندارد!",
            show_alert=True,
        )
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()

    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if isinstance(callback_data, RenewSelectService.Callback) and callback_data.menu_id:
        menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
        has_prev = True
        sub_menues = ServiceMenu.filter(parent_id=callback_data.menu_id, renew=True)
        services = menu.services.filter()
    else:
        menu = None
        has_prev = False
        sub_menues = ServiceMenu.filter(parent_id=None, renew=True)
        # find services which dont belong to any menu
        services = Service.filter(
            Q(
                id__not_in=RawSQL("(SELECT `service_id` FROM `services_to_menues`)"),
            )
        )
    services = services.filter(
        Q(user_filter=False) | Q(user_filters__id=user.id),
        server__is_enabled=True,
        renewable=True,
        server_id=proxy.server_id,
        one_time_only=False,
        is_test_service=False,
    )

    if user.role == User.Role.user:
        services = services.filter(resellers_only=False)
        sub_menues = sub_menues.filter(resellers_only=False)
    elif user.role == User.Role.reseller:
        services = services.filter(users_only=False)
        sub_menues = sub_menues.filter(users_only=False)

    if not await services.all().count() and not await sub_menues.all().count():
        text = """
❗️برای اشتراک مورد نظر امکان تمدید وجود ندارد!
لطفا با پشتیبانی تماس بگیرید.
    """
        return await query.answer(text, show_alert=True)

    default = "برای تمدید اشتراک میتونید یکی از سرویس‌های زیر رو انتخاب کنید:"
    if menu:
        default = menu.description or default
    text = f"""
♻️ از این بخش میتونید اشتراک خریداری‌شده خودتون رو تمدید کنید!

{default}
    """
    mns = [
        (sm.id, sm.title, sm.button_icon, sm.button_style)
        for sm in await sub_menues.all()
    ]
    svs = [
        (
            service.id,
            await service.get_display_name(user=user, type="renew"),
            service.button_icon,
            service.button_style,
        )
        for service in await services.all()
    ]

    await query.message.edit_text(
        text,
        reply_markup=RenewSelectService(
            proxy_id=proxy.id,
            sub_menues=mns,
            services=svs,
            menu_id=menu.id if menu else 0,
            parent_menu_id=menu.parent_id if menu else 0,
            has_previous=has_prev,
            current_page=callback_data.current_page,
            user_id=callback_data.user_id,
        ).as_markup(),
    )


@router.callback_query(RenewSelectService.Callback.filter())
async def renew_proxy_service(
    query: CallbackQuery,
    user: User,
    callback_data: RenewSelectService.Callback,
    state: FSMContext = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    text = """
✅ برای تمدید میتونید یکی از حالت‌های زیر رو انتخاب کنید👇

➖ تمدید آنی: دوره جدید اشتراک شما از همین لحظه محاسبه می‌شود و سرویس جدید برای شما فعال می‌شود.

➖ رزور پلن پشتیبان: پس از اتمام حجم یا دوره اشتراک فعلی، سرویس جدید به طور خودکار فعال می‌شود.

یکی از حالت‌های تمدید رو انتخاب کنید👇
    """
    await query.message.edit_text(
        text,
        reply_markup=RenewSelectMethod(
            proxy_id=proxy.id,
            service_id=callback_data.service_id,
            menu_id=callback_data.menu_id,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
        ).as_markup(),
    )


@router.callback_query(RenewSelectMethod.Callback.filter(F.method == RenewMethods.now))
async def renew_proxy_now(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: RenewSelectMethod.Callback,
    invoice_id: int = None,
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    service = await Service.filter(
        Q(user_filter=False) | Q(user_filters__id=user.id),
        id=callback_data.service_id,
        renewable=True,
        server__is_enabled=True,
        is_test_service=False,
    ).first()
    if not service:
        text = "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text, show_alert=True)
        return await qmsg.answer(text)

    price = await service.get_price()
    await user.fetch_related("setting")
    discount_percentage = None

    if user.setting and (discount_percentage := user.setting.discount_percentage):
        discounted_price = await service.get_price(discount_percent=discount_percentage)
        discount = None
    else:
        discount = await service.get_discount(user=user, type="renew")
        if discount:
            discounted_price = await service.get_price(discount=discount)
            discount_percentage = discount.percentage
        else:
            discounted_price = price
            discount_percentage = None

    balance = await user.get_available_credit()

    await proxy.fetch_related("service")

    if callback_data.confirmed:
        if await RateLimit.throttled(qmsg, user.id, "renew_now", count=1, duration=8):
            return
        if callback_data.discount_id and (
            discount is None or discount.id != callback_data.discount_id
        ):
            await qmsg.answer(
                "❌ کد تخفیف اعمال شده شما منقضی شده است! لطفا دوباره تلاش کنید."
            )
            return await renew_proxy_now(
                qmsg=qmsg,
                user=user,
                callback_data=RenewSelectMethod.Callback(
                    proxy_id=proxy.id,
                    service_id=callback_data.service_id,
                    menu_id=callback_data.menu_id,
                    user_id=callback_data.user_id,
                    current_page=callback_data.current_page,
                    method=callback_data.method,
                ),
            )
        if balance < discounted_price:
            if isinstance(qmsg, CallbackQuery):
                text = "❌ موجودی حساب شما کافی نمی‌باشد!"
                return await qmsg.answer(text, show_alert=True)
            return await qmsg.answer(text)

        if is_locked(user_id=user.id):
            return

        with lock(user_id=user.id):
            try:
                async with in_transaction():
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
                        invoice.amount = discounted_price
                        await invoice.save(
                            update_fields=["is_draft", "is_paid", "proxy_id", "amount"]
                        )
                    else:
                        await Invoice.create(
                            amount=discounted_price,
                            type=Invoice.Type.renew_now,
                            is_paid=not user.is_postpaid,
                            service=service,
                            proxy=proxy,
                            user=user,
                        )
                    panel = get_panel(service.server_id)
                    if getattr(panel, "panel_managed_billing", False):
                        # Guardino: renew is a single hub op (reset + recharge),
                        # priced by the hub from days/total_gb.
                        cfg = service.panel_config or {}
                        days = (
                            service.expire_duration // 86400
                            if service.expire_duration
                            else 0
                        )
                        total_gb = int(
                            cfg.get("total_gb")
                            or (
                                (service.data_limit // (1024**3))
                                if service.data_limit
                                else 0
                            )
                        )
                        await panel.renew_user(
                            proxy.username,
                            days=days,
                            total_gb=total_gb,
                            pricing_mode=cfg.get("pricing_mode", "bundle"),
                        )
                        if service.id != proxy.service_id:
                            proxy.service_id = service.id
                        sv_proxy = await panel.get_user(proxy.username)
                        if sv_proxy:
                            proxy.status = sv_proxy.status.value
                        proxy.cost = discounted_price
                        await proxy.save()
                    else:
                        data_limit = service.data_limit
                        # read remaining BEFORE reset, when carrying over data
                        if (
                            data_limit
                            and proxy.service
                            and proxy.service.data_limit
                            and proxy.service.append_available_data_renew
                        ):
                            existing = await panel.get_user(proxy.username)
                            if existing:
                                data_limit = data_limit + (
                                    (existing.data_limit or 0) - existing.used_traffic
                                )
                        sv_proxy = await panel.reset_usage(proxy.username)
                        if not sv_proxy:
                            raise ApiUserError(
                                "reset data usage didn't return anything!"
                            )
                        if service.id != proxy.service_id:
                            proxy.service_id = service.id
                        params = await panel.service_modify_params(
                            service, existing=sv_proxy
                        )
                        params.expire = (
                            helpers.get_expire_timestamp(service.expire_duration)
                            if service.expire_duration
                            else 0
                        )
                        params.data_limit = data_limit
                        params.data_limit_reset_strategy = (
                            service.usage_reset_strategy.value
                            if service.data_limit
                            else service.UsageResetStrategy.no_reset.value
                        )
                        sv_proxy = await panel.modify_user(proxy.username, params)
                        proxy.status = sv_proxy.status.value
                        proxy.cost = discounted_price
                        await proxy.save()
                    if discount:
                        discount.used_times = TF("used_times") + 1
                        await discount.save(update_fields=["used_times"])
                        await discount.used_by.add(user)
                    if not sv_proxy:
                        raise ApiUserError("modify user didn't return anything!")
                text = "✅ سرویس شما با موفقیت تمدید شد!"
                if isinstance(qmsg, CallbackQuery):
                    await qmsg.answer(text, show_alert=True)
                else:
                    await qmsg.answer(text)
                helpers.order_log(
                    proxy=proxy,
                    type="renew",
                    service=service,
                    user=user,
                    amount_paid=discounted_price,
                )
                await show_proxy(
                    qmsg,
                    user,
                    callback_data=Proxies.Callback(
                        proxy_id=proxy.id,
                        user_id=callback_data.user_id,
                        action=ProxiesActions.show_proxy,
                        current_page=callback_data.current_page,
                    ),
                )
                return
            except Exception as err:
                text = "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
                if isinstance(qmsg, CallbackQuery):
                    await qmsg.answer(text, show_alert=True)
                else:
                    await qmsg.answer(text)
                raise err

    text = f"""
🌀 آیا مایل به فعال سازی سرویس زیر برای این پروکسی هستید؟

💎 {service.name}
🕐 مدت زمان: {helpers.hr_time(service.expire_duration, lang="fa") if service.expire_duration else '♾'}
🖥 حجم: {helpers.hr_size(service.data_limit, lang="fa") if service.data_limit else '♾'}
💰 قیمت: {price:,} تومان
"""
    if discounted_price < price:
        text += f"""
~~~~~~~~~~~~~~~~~~~~~~~~
🔥 تخفیف ویژه شما: <code>{discount_percentage}</code> درصد
💰 قیمت با تخفیف: <code>{discounted_price:,}</code> تومان
~~~~~~~~~~~~~~~~~~~~~~~~
"""
    text += f"""
🏦 موجودی حساب شما: {balance:,} تومان
💵 مبلغ قابل پرداخت: {discounted_price:,} تومان
~~~~~~~~~~~~~~~~~~~~~~~~
    """
    if (
        service.data_limit
        and proxy.service
        and proxy.service.data_limit
        and proxy.service.append_available_data_renew
    ):
        text += """
❕حجم باقیمانده اشتراک شما به دوره بعد منتقل خواهد شد       
~~~~~~~~~~~~~~~~~~~~~~~~
        """
    if balance >= discounted_price:
        text += "🛍 برای تمدید آنی و فعالسازی سرویس، دکمه زیر را کلیک کنید👇"
        markup = ConfirmRenew(
            proxy_id=proxy.id,
            service_id=service.id,
            menu_id=callback_data.menu_id,
            method=RenewMethods.now,
            user_id=callback_data.user_id,
            discount_id=discount.id if discount is not None else None,
            current_page=callback_data.current_page,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=markup)
        return await qmsg.answer(text, reply_markup=markup)
    text += "😞 موجودی حساب شما برای فعالسازی این سرویس کافی نیست! برای افزایش اعتبار دکمه زیر را کلیک کنید👇"
    markup = ConfirmRenew(
        proxy_id=proxy.id,
        service_id=service.id,
        menu_id=callback_data.menu_id,
        method=RenewMethods.now,
        user_id=callback_data.user_id,
        discount_id=discount.id if discount is not None else None,
        current_page=callback_data.current_page,
        has_balance=False,
        pay_amount=discounted_price - balance,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


@router.callback_query(
    RenewSelectMethod.Callback.filter(F.method == RenewMethods.reserve)
)
async def renew_proxy_reserve(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: RenewSelectMethod.Callback,
    invoice_id: int = None,
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = await Proxy.filter(id=callback_data.proxy_id).first()
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    service = await Service.filter(
        Q(user_filter=False) | Q(user_filters__id=user.id),
        id=callback_data.service_id,
        renewable=True,
        server__is_enabled=True,
        is_test_service=False,
    ).first()
    if not service:
        text = "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.answer(text, show_alert=True)
        return await qmsg.answer(text)

    price = await service.get_price()
    await user.fetch_related("setting")
    discount_percentage = None

    if user.setting and (discount_percentage := user.setting.discount_percentage):
        discounted_price = await service.get_price(discount_percent=discount_percentage)
        discount = None
    else:
        discount = await service.get_discount(user=user, type="renew")
        if discount:
            discounted_price = await service.get_price(discount=discount)
            discount_percentage = discount.percentage
        else:
            discounted_price = price
            discount_percentage = None

    balance = await user.get_available_credit()

    if callback_data.confirmed:
        if await RateLimit.throttled(qmsg, user.id, "reserve", count=1, duration=8):
            return
        if callback_data.discount_id and (
            discount is None or discount.id != callback_data.discount_id
        ):
            text = "❌ کد تخفیف اعمال شده شما منقضی شده است! لطفا دوباره تلاش کنید."
            await qmsg.answer(text)

            return await renew_proxy_reserve(
                qmsg=qmsg,
                user=user,
                callback_data=RenewSelectMethod.Callback(
                    proxy_id=proxy.id,
                    service_id=callback_data.service_id,
                    menu_id=callback_data.menu_id,
                    user_id=callback_data.user_id,
                    current_page=callback_data.current_page,
                    method=callback_data.method,
                ),
            )
        if balance < discounted_price:
            text = "❌ موجودی حساب شما کافی نمی‌باشد!"
            if isinstance(qmsg, CallbackQuery):
                return await qmsg.answer(text, show_alert=True)
            return await qmsg.answer(text)
        try:
            async with in_transaction():
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
                    invoice.amount = discounted_price
                    await invoice.save(
                        update_fields=["is_draft", "is_paid", "proxy_id", "amount"]
                    )
                else:
                    invoice = await Invoice.create(
                        amount=discounted_price,
                        type=Invoice.Type.renew_reserve,
                        is_paid=True,
                        service=service,
                        proxy=proxy,
                        user=user,
                    )
                sv_proxy = await get_panel(service.server_id).get_user(proxy.username)
                if not sv_proxy:
                    raise ApiUserError("reset data usage didn't return anything!")
                if not sv_proxy.status == PanelUserStatus.active:
                    text = "🚫 به دلیل فعال نبودن اشتراک در حال حاضر امکان رزرو پلن پشتیبان وجود ندارد!"
                    if isinstance(qmsg, CallbackQuery):
                        return await qmsg.answer(text, show_alert=True)
                    return await qmsg.answer(text)

                reserve = await Reserve.create(
                    activate_at=dt.fromtimestamp(sv_proxy.expire - 600, UTC)
                    if sv_proxy.expire
                    else None,
                    invoice=invoice,
                    proxy=proxy,
                    service=service,
                    user=user,
                )
                if service.id != proxy.service_id:
                    proxy.service_id = service.id
                proxy.status = sv_proxy.status.value
                await proxy.save()
                if discount:
                    discount.used_times = TF("used_times") + 1
                    await discount.save(update_fields=["used_times"])
                    await discount.used_by.add(user)
                if not sv_proxy:
                    raise ApiUserError("modify user didn't return anything!")
                text = """
✅ پلن پشتیبان با موفقیت برای شما رزرو شد!
"""
                if reserve.activate_at:
                    text += f"""
⏳ پلن پشتیبان به صورت خودکار در تاریخ {helpers.hr_date(reserve.activate_at.timestamp())} یا به محض تمام شدن حجم پلن فعلی فعال خواهد شد.
"""
                else:
                    text += """
⏳ پلن پشتیبان به محض تمام شدن حجم پلن فعلی فعال خواهد شد.
"""
                if isinstance(qmsg, CallbackQuery):
                    await qmsg.answer(text, show_alert=True)
                else:
                    await qmsg.answer(text)
                helpers.order_log(
                    proxy=proxy,
                    type="reserve",
                    service=service,
                    user=user,
                    amount_paid=discounted_price,
                    reserve=reserve,
                )
                await show_proxy(
                    qmsg,
                    user,
                    callback_data=Proxies.Callback(
                        proxy_id=proxy.id,
                        user_id=callback_data.user_id,
                        action=ProxiesActions.show_proxy,
                        current_page=callback_data.current_page,
                    ),
                )
                return
        except Exception as err:
            text = "❌ خطایی در انجام عملیات رخ داد! لطفا با پشتیبانی تماس بگیرید."
            if isinstance(qmsg, CallbackQuery):
                await qmsg.answer(text, show_alert=True)
            else:
                await qmsg.answer(text)
            raise err

    text = f"""
🌀 آیا مایل به فعال سازی پلن زیر به عنوان پشتیبان برای این پروکسی هستید؟

💎 {service.name}
🕐 مدت زمان: {helpers.hr_time(service.expire_duration, lang="fa") if service.expire_duration else '♾'}
🖥 حجم: {helpers.hr_size(service.data_limit, lang="fa") if service.data_limit else '♾'}
💰 قیمت: {price:,} تومان
"""
    if discounted_price < price:
        text += f"""
~~~~~~~~~~~~~~~~~~~~~~~~
🔥 تخفیف ویژه شما: <code>{discount_percentage}</code> درصد
💰 قیمت با تخفیف: <code>{discounted_price:,}</code> تومان
~~~~~~~~~~~~~~~~~~~~~~~~
"""
    text += f"""
🏦 موجودی حساب شما: {balance:,} تومان
💵 مبلغ قابل پرداخت: {discounted_price:,} تومان
~~~~~~~~~~~~~~~~~~~~~~~~
    """
    await proxy.fetch_related("service")
    if (
        service.data_limit
        and proxy.service
        and proxy.service.data_limit
        and proxy.service.append_available_data_renew
    ):
        text += """
❕حجم باقیمانده اشتراک شما به دوره بعد منتقل خواهد شد       
~~~~~~~~~~~~~~~~~~~~~~~~
        """
    if balance >= discounted_price:
        text += "🛍 برای رزرو پلن پشتیبان و فعالسازی خودکار در زمان اتمام پلن فعلی، دکمه زیر را کلیک کنید👇"
        markup = ConfirmRenew(
            proxy_id=proxy.id,
            service_id=service.id,
            menu_id=callback_data.menu_id,
            method=RenewMethods.reserve,
            user_id=callback_data.user_id,
            discount_id=discount.id if discount is not None else None,
            current_page=callback_data.current_page,
        ).as_markup()
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text, reply_markup=markup)
        return await qmsg.answer(text, reply_markup=markup)
    text += "😞 موجودی حساب شما برای فعالسازی این سرویس کافی نیست! برای افزایش اعتبار دکمه زیر را کلیک کنید👇"
    markup = ConfirmRenew(
        proxy_id=proxy.id,
        service_id=service.id,
        method=RenewMethods.reserve,
        menu_id=callback_data.menu_id,
        user_id=callback_data.user_id,
        discount_id=discount.id if discount is not None else None,
        current_page=callback_data.current_page,
        has_balance=False,
        pay_amount=discounted_price - balance,
    ).as_markup()
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.edit_text(text, reply_markup=markup)
    return await qmsg.answer(text, reply_markup=markup)


@router.callback_query(ReservePanel.Callback.filter(F.confirmed == False))  # noqa: E712
@router.callback_query(
    ProxyPanel.Callback.filter(F.action == ProxyPanelActions.show_reserve)
)
async def show_reserve(
    query: CallbackQuery,
    user: User,
    callback_data: ProxyPanel.Callback | ReservePanel.Callback,
):
    if helpers.reserve_job_queued(callback_data.proxy_id):
        return query.answer(
            "❕پلن پشتیبان شما لحظاتی دیگر به صورت خودکار فعال خواهد شد!"
        )
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = (
        await Proxy.filter(id=callback_data.proxy_id)
        .prefetch_related("reserve")
        .first()
    )
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if not proxy.reserve:
        return await query.answer("❌ پلن پشتیبانی برای این اشتراک خریداری نشده است!")

    await proxy.reserve.fetch_related("service")
    service = proxy.reserve.service
    text = f"""
🌀 پلن پشتیبان خریداری شده برای این اشتراک:

💎 {service.name}
🕐 مدت زمان: {helpers.hr_time(service.expire_duration, lang="fa") if service.expire_duration else '♾'}
🖥 حجم: {helpers.hr_size(service.data_limit, lang="fa") if service.data_limit else '♾'}
🕐 زمان فعال شدن: {helpers.hr_date(proxy.reserve.activate_at.timestamp()) if proxy.reserve.activate_at else '➖'}
~~~~~~~~~~~~~~~~~~~~~~~~
💡 اگر مایل به فعالسازی پلن پشتیبان در این لحظه هستید دکمه «فعالسازی» را کلیک کنید

♻️ برای لغو کردن پلن پشتیبان از دکمه «لغو» استفاده کنید. توجه کنید که فقط تا ۳ روز بعد از خرید پلن پشتیبان امکان لغو آن وجود خواهد داشت!
"""
    cancelable = (proxy.reserve.created_at + td(days=3)) > dt.now(UTC)
    if isinstance(callback_data, ReservePanel.Callback):
        if callback_data.action == ReservePanelAction.activate:
            warning = "❗️ مطمئن هستید که میخواهید پلن پشتیبان در این لحظه فعال شود؟ دکمه «فعالسازی» را دوباره کلیک کنید!"
            await query.answer(warning, show_alert=True)
            return await query.message.edit_text(
                text + "~~~~~~~~~~~~~~~~~~~~~~~~\n" + warning,
                reply_markup=ReservePanel(
                    proxy=proxy,
                    user_id=callback_data.user_id,
                    current_page=callback_data.current_page,
                    cancelable=cancelable,
                    confirmed=True,
                ).as_markup(),
            )
        elif callback_data.action == ReservePanelAction.cancel:
            warning = "❗️ مطمئن هستید که میخواهید پلن پشتیبان را لغو کنید؟ دکمه «لغو پلن پشتیبان» را دوباره کلیک کنید!"
            await query.answer(warning, show_alert=True)
            return await query.message.edit_text(
                text + "~~~~~~~~~~~~~~~~~~~~~~~~\n" + warning,
                reply_markup=ReservePanel(
                    proxy=proxy,
                    user_id=callback_data.user_id,
                    current_page=callback_data.current_page,
                    cancelable=cancelable,
                    action=callback_data.action,
                    confirmed=True,
                ).as_markup(),
            )
    await query.message.edit_text(
        text,
        reply_markup=ReservePanel(
            proxy=proxy,
            user_id=callback_data.user_id,
            current_page=callback_data.current_page,
            cancelable=cancelable,
            confirmed=False,
        ).as_markup(),
    )


@router.callback_query(
    ReservePanel.Callback.filter(
        (F.action == ReservePanelAction.activate) & (F.confirmed == True)  # noqa: E712
    )
)
async def activate_reserve_handler(
    query: CallbackQuery, user: User, callback_data: ReservePanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = (
        await Proxy.filter(id=callback_data.proxy_id)
        .prefetch_related("reserve")
        .first()
    )
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if not proxy.reserve:
        return await query.answer("❌ پلن پشتیبانی برای این اشتراک خریداری نشده است!")

    scheduler.add_job(
        activate_reserve,
        "date",
        id=f"reserves:queue:{proxy.id}",
        args=(proxy.id,),
        run_date=dt.utcnow() + td(seconds=30),
    )
    await query.answer(
        "✅ پلن پشتیبان شما تا لحظاتی دیگر فعال خواهد شد! لطفا کمی صبر کنید.",
        show_alert=True,
    )
    await show_proxy(
        query,
        user,
        callback_data=Proxies.Callback(
            proxy_id=proxy.id,
            user_id=callback_data.user_id,
            action=ProxiesActions.show_proxy,
            current_page=callback_data.current_page,
        ),
    )


@router.callback_query(
    ReservePanel.Callback.filter(
        (F.action == ReservePanelAction.cancel) & (F.confirmed == True)  # noqa: E712
    )
)
async def cancel_reserve_handler(
    query: CallbackQuery, user: User, callback_data: ReservePanel.Callback
):
    user_id = callback_data.user_id if callback_data.user_id else user.id
    proxy = (
        await Proxy.filter(id=callback_data.proxy_id)
        .prefetch_related("reserve")
        .first()
    )
    if (user.role < user.Role.admin) and (user.id != user_id):
        return
    elif (user.role == user.Role.admin) and (proxy.user_id != user_id):
        await proxy.fetch_related("user")
        if proxy.user.parent_id != user.id:
            return

    if not proxy.reserve:
        return await query.answer("❌ پلن پشتیبانی برای این اشتراک خریداری نشده است!")

    async with in_transaction():
        try:
            scheduler.remove_job(f"reserves:queue:{proxy.id}")
        except JobLookupError:
            pass
        await Invoice.filter(id=proxy.reserve.invoice_id).delete()
        await Reserve.filter(proxy_id=proxy.id).delete()
    await query.answer(
        "✅ پلن پشتیبان سرویس شما حذف شد.",
        show_alert=True,
    )
    await show_proxy(
        query,
        user,
        callback_data=Proxies.Callback(
            proxy_id=proxy.id,
            user_id=callback_data.user_id,
            action=ProxiesActions.show_proxy,
            current_page=callback_data.current_page,
        ),
    )


@router.message(IsSubscriptionURL())
async def add_user_from_subscription(
    message: Message,
    user: User,
    token: str,
):
    for server_id, client in Marzban.get_servers().items():
        try:
            sv_user = await user_subscription_info.asyncio(token=token, client=client)
            if not sv_user:
                continue
            proxy = await Proxy.filter(username=sv_user.username).first()
            if proxy:
                await Proxy.filter(username=sv_user.username).update(user_id=user.id)
            else:
                proxy = await Proxy.create(
                    username=sv_user.username,
                    status=sv_user.status,
                    user_id=user.id,
                    server_id=server_id,
                )
            await proxy.refresh_from_db()
            return await message.reply(
                "✅ اشتراک مورد نظر از طریق لینک اتصال هوشمند به حساب شما منتقل شد!",
                reply_markup=ProxySettings(proxy=proxy).as_markup(),
            )
        except anyio.EndOfStream:
            pass
        except Exception as exc:
            logger.error(f"Error in finding subscription in server {server_id}: {exc}")

    return await message.reply(
        "❌ لینک اتصال هوشمند مورد نظر در سرورهای ربات یافت نشد!"
    )
