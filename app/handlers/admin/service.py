import asyncio
import json
import re

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.keyboards.admin.admin import (
    AdminPanel,
    AdminPanelAction,
    BulkUpdateProxies,
    BulkUpdateProxiesProc,
    CancelFormAdmin,
    YesOrNoFormAdmin,
)
from app.keyboards.admin.service import (
    USAGE_RESET_STRATEGY,
    ConfirmServiceAction,
    EditService,
    EditServiceAction,
    SelectGroups,
    SelectInbounds,
    SelectNodes,
    SelectServer,
    SelectServicesBulk,
    ServiceAct,
    ServiceActAction,
    ServiceActLimit,
    ServiceActLimitAction,
    ServiceActLimitUsers,
    Services,
    ServicesAction,
    ServicesPriority,
)
from app.main import redis
from app.marzban import Marzban
from app.panels import get_panel, PanelError
from app.logger import get_logger
from app.models.proxy import Proxy
from app.models.server import Server
from app.models.service import Service
from app.models.user import User
from app.utils import helpers, proxy_management
from app.utils.filters import IsSuperUser
from marzban_client.api.system import get_inbounds

from . import router

logger = get_logger("handlers/admin/service")

def _is_pasarguard(server: Server) -> bool:
    """Whether a Server speaks PasarGuard (group-based provisioning)."""
    return str(getattr(server.panel_type, "value", server.panel_type)) == "pasarguard"


def _is_guardino(server: Server) -> bool:
    """Whether a Server speaks Guardino Hub (node-based, id-keyed)."""
    return str(getattr(server.panel_type, "value", server.panel_type)) == "guardino"


async def _fetch_panel_catalog(
    server: Server, key: str
) -> tuple[list | None, str | None]:
    """Fetch the panel's selectable catalog (``groups`` for PasarGuard /
    ``nodes`` for Guardino) via the adapter.

    Returns ``(items, None)`` on success or ``(None, message)`` on failure so
    the caller surfaces a clear Persian error instead of letting a ``PanelError``
    bubble up unhandled — which previously looked like "nothing happens" when an
    admin picked a PasarGuard/Guardino server while building a service. The raw
    panel detail is logged (not shown) per the no-secret-leak rule.
    """
    try:
        catalog = await get_panel(server.id).get_inbounds()
        return list(catalog.get(key, []) or []), None
    except PanelError as exc:
        logger.warning("server %s get_inbounds failed: %s", server.id, exc)
        code = getattr(exc, "status_code", None)
        return None, (
            "❌ ارتباط با پنل برقرار نشد"
            + (f" (کد {code})" if code else "")
            + ".\nاتصال، آدرس و توکن/رمز سرور را بررسی کنید و دوباره سرور را انتخاب کنید."
        )
    except KeyError:
        logger.warning("server %s has no cached panel adapter", server.id)
        return None, (
            "❌ آداپتر این سرور یافت نشد. ربات را یک‌بار ری‌استارت کنید یا سرور را دوباره اضافه کنید."
        )
    except Exception:  # noqa: BLE001 - never silently swallow
        logger.exception("server %s get_inbounds crashed", server.id)
        return None, (
            "❌ خطای ناشناخته در دریافت اطلاعات از پنل. لاگ سرور را بررسی کنید."
        )


cancel_form = CancelFormAdmin().as_markup(resize_keyboard=True, one_time_only=True)
yes_or_no_form = YesOrNoFormAdmin().as_markup(
    resize_keyboard=True, one_time_keyboard=True
)


class AddServiceForm(StatesGroup):
    name = State()
    data_limit = State()
    expire_duration = State()
    server_id = State()
    inbounds = State()
    price = State()
    confirm = State()


class EditServiceForm(StatesGroup):
    id = State()
    name = State()
    data_limit = State()
    expire_duration = State()
    inbounds = State()
    price = State()
    apply_services = State()


@router.message(
    F.text.casefold() == "cancel", IsSuperUser(), StateFilter(AddServiceForm)
)
@router.message(
    F.text == CancelFormAdmin.cancel,
    IsSuperUser(),
    StateFilter(AddServiceForm, EditServiceForm),
)
@router.message(Command("cancel"), IsSuperUser(), StateFilter(AddServiceForm))
@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.services), IsSuperUser()
)
async def show_services(
    query: CallbackQuery | Message, user: User, state: FSMContext | None = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="Canceled!", reply_markup=ReplyKeyboardRemove())
    count = await Service.all().count()
    if count:
        text = (
            f"لیست سرویس‌های اضافه شده ({count}):\nراهنما: https://t.me/c/2001448048/39"
        )
        services = Services(services=await Service.all()).as_markup()
        if isinstance(query, CallbackQuery):
            return await query.message.edit_text(text=text, reply_markup=services)
        return await query.answer(text=text, reply_markup=services)
    text = "سرویسی اضافه نشده‌است!\nراهنما: https://t.me/c/2001448048/39"
    services = Services(services=[]).as_markup()
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text(text=text, reply_markup=services)
    return await query.answer(text=text, reply_markup=services)


@router.callback_query(
    Services.Callback.filter(F.action == ServicesAction.sv_priorities), IsSuperUser()
)
async def show_service_priorities(query: CallbackQuery, user: User):
    count = await Service.all().count()
    if not count:
        return await query.answer("سرویس اضافه نشده است!", show_alert=True)
    text = f"لیست سرویس‌های اضافه شده ({count}):\nراهنما: https://t.me/c/2001448048/39"
    services = ServicesPriority(services=await Service.all()).as_markup()
    return await query.message.edit_text(text=text, reply_markup=services)


@router.callback_query(
    ServicesPriority.Callback.filter(F.service_id != 0), IsSuperUser()
)
async def change_service_priorities(
    query: CallbackQuery, user: User, callback_data: ServicesPriority.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_service_priorities(query, user)

    try:
        await service.change_priority(callback_data.direction)
    except ValueError:
        return await query.answer(text="!!")

    return await show_service_priorities(query, user)


# Add Services
@router.callback_query(
    Services.Callback.filter(F.action == ServicesAction.add),
    IsSuperUser(),
)
async def add_service(query: CallbackQuery, user: User, state: FSMContext):
    await state.set_state(AddServiceForm.name)
    await query.message.answer("نام سرویس را وارد کنید:", reply_markup=cancel_form)


@router.message(
    AddServiceForm.name,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_name(message: Message, user: User, state: FSMContext):
    if await Service.filter(name=message.text).first():
        return message.answer(
            "سرویسی با این نام قبلا اضافه شده‌است! دوباره وارد کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(name=message.text)
    await state.set_state(AddServiceForm.data_limit)
    await message.answer(
        "مقدار حجم سرویس را به گیگابایت وارد کنید (برای نامحدود 0 را وارد کنید):",
        reply_markup=cancel_form,
    )


@router.message(
    AddServiceForm.data_limit,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_data_limit(message: Message, user: User, state: FSMContext):
    try:
        if float(message.text) < 0:
            return await message.answer(
                message.chat.id,
                "❌ مقدار باید بیشتر یا مساوی 0 باشد",
                reply_markup=cancel_form(),
            )
        data_limit = float(message.text) * 1024 * 1024 * 1024
    except ValueError:
        return await message.answer(
            "مقدار باید عدد صحیح یا اعشار باشد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(data_limit=data_limit)
    await state.set_state(AddServiceForm.expire_duration)
    text = """
مدت دوره زمانی سرویس را به فرمت زیر وارد کنید:
^[0-9]{1,3}(D|M|Y|H)

مثال:
18h -> ۱۸ ساعت
3d -> سه روز
1m -> یک ماه
1y -> یک سال

(برای نامحدود 0 را وارد کنید)
"""
    await message.answer(text=text, reply_markup=cancel_form)


@router.message(
    AddServiceForm.expire_duration,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_expire_duration(message: Message, user: User, state: FSMContext):
    try:
        if message.text.isnumeric() and int(message.text) == 0:
            expire_duration = 0
        elif re.match(r"^[0-9]{1,3}(M|m|Y|y|D|d|H|h)$", message.text):
            expire_duration = 0
            number_pattern = r"^[0-9]{1,3}"
            number = int(re.findall(number_pattern, message.text)[0])
            symbol_pattern = r"(M|m|Y|y|D|d|H|h)$"
            symbol = re.findall(symbol_pattern, message.text)[0].upper()
            if symbol == "H":
                expire_duration = 3600 * number
            elif symbol == "D":
                expire_duration += 86400 * number
            elif symbol == "M":
                expire_duration += 2678400 * number
            elif symbol == "Y":
                expire_duration = 31104000 * number
        else:
            raise ValueError("خطایی در دریافت مدت زمان رخ داد! دوباره تلاش کنید:")
    except ValueError:
        return await message.answer(
            "❌ فرمت ارسالی نامعتبر است! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(expire_duration=expire_duration)
    await state.set_state(AddServiceForm.price)
    await message.answer("مبلغ سرویس را به تومان وارد کنید:", reply_markup=cancel_form)


@router.message(
    AddServiceForm.price,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_price(message: Message, user: User, state: FSMContext):
    try:
        await state.update_data(price=int(message.text))
        await state.set_state(AddServiceForm.server_id)
        servers = await Server.all()
        await message.answer(
            "یکی از سرورهای زیر را برای این سرویس انتخاب کنید::",
            reply_markup=SelectServer(servers=servers).as_markup(),
        )
    except ValueError:
        return await message.answer("مبلغ باید مقداری عددی باشد! دوباره تلاش کنید:")


@router.callback_query(
    AddServiceForm.server_id, IsSuperUser(), SelectServer.Callback.filter()
)
async def get_service_server_id(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectServer.Callback,
):
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        return await query.answer(
            text=f"خطایی در دریافت سرور {callback_data.server_id!r} رخ داد!"
        )
    await state.update_data(server_id=callback_data.server_id)
    data = await state.get_data()
    info = f"""
نام: <b>{data.get('name')}</b>
حجم: <b>{helpers.hr_size(data.get('data_limit')) if data.get('data_limit') else '♾'}</b>
اعتبار زمانی: <b>{helpers.hr_time(data.get('expire_duration')) if data.get('expire_duration') else '♾'}</b>
مبلغ: <b>{data.get('price')}</b>
سرور: <b>{server.identifier}</b>
"""
    await state.set_state(AddServiceForm.inbounds)

    if _is_guardino(server):
        ed = data.get("expire_duration") or 0
        if 0 < ed < 86400:
            # Guardino only supports whole days; block a sub-day service here.
            await state.set_state(AddServiceForm.expire_duration)
            return await query.message.answer(
                "❌ گاردینو مدت کمتر از ۱ روز را پشتیبانی نمی‌کند.\n"
                "لطفاً مدت سرویس را حداقل ۱ روز وارد کنید (مثلاً 1d یا 1m):",
                reply_markup=cancel_form,
            )
        nodes, err = await _fetch_panel_catalog(server, "nodes")
        if err is not None:
            await state.set_state(AddServiceForm.server_id)
            return await query.message.answer(err)
        await state.update_data(node_ids=[])
        return await query.message.edit_text(
            info + "\nنودهای این سرور را انتخاب کنید (اختیاری — خالی = نودهای پیش‌فرض هاب):",
            reply_markup=SelectNodes(
                nodes=nodes, selected_node_ids=[], server_id=server.id
            ).as_markup(),
        )

    if _is_pasarguard(server):
        groups, err = await _fetch_panel_catalog(server, "groups")
        if err is not None:
            await state.set_state(AddServiceForm.server_id)
            return await query.message.answer(err)
        if not groups:
            await state.set_state(AddServiceForm.server_id)
            return await query.message.answer(
                "❌ این پنل پاسارگارد هیچ گروهی (Group) ندارد.\n"
                "ابتدا در پنل پاسارگارد یک گروه بسازید، سپس دوباره سرور را انتخاب کنید."
            )
        await state.update_data(group_ids=[])
        return await query.message.edit_text(
            info + "\nگروه‌های این سرور را انتخاب کنید:",
            reply_markup=SelectGroups(
                groups=groups, selected_group_ids=[], server_id=server.id
            ).as_markup(),
        )

    inbounds: dict[str, list[str]] = {
        protocol: [inbound.tag for inbound in protocol_inbounds]
        for protocol, protocol_inbounds in (
            await get_inbounds.asyncio(client=Marzban.get_server(server.id))
        ).additional_properties.items()
    }
    await query.message.edit_text(
        info + "\nاینباند‌های این سرور را انتخاب کنید:",
        reply_markup=SelectInbounds(
            inbounds=inbounds,
            selected_inbounds={},
            server_id=callback_data.server_id,
        ).as_markup(),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.edit_inbounds),
    IsSuperUser(),
)
async def edit_service_inbounds(
    query: Message,
    user: User,
    state: FSMContext,
    callback_data: ServiceAct.Callback,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    server = await Server.filter(id=service.server_id).first()
    await state.set_state(EditServiceForm.inbounds)
    if server and _is_guardino(server):
        nodes, err = await _fetch_panel_catalog(server, "nodes")
        if err is not None:
            await state.clear()
            return await query.answer(err, show_alert=True)
        selected = list((service.panel_config or {}).get("node_ids", []))
        await state.update_data(node_ids=selected)
        return await query.message.edit_text(
            "نودها را انتخاب کنید و ذخیره را کلیک کنید:",
            reply_markup=SelectNodes(
                nodes=nodes,
                selected_node_ids=selected,
                server_id=service.server_id,
                for_edit=True,
                service_id=service.id,
            ).as_markup(),
        )

    if server and _is_pasarguard(server):
        groups, err = await _fetch_panel_catalog(server, "groups")
        if err is not None:
            await state.clear()
            return await query.answer(err, show_alert=True)
        selected = list((service.panel_config or {}).get("group_ids", []))
        await state.update_data(group_ids=selected)
        return await query.message.edit_text(
            "گروه‌ها را انتخاب کنید و زخیره را کلیک کنید:",
            reply_markup=SelectGroups(
                groups=groups,
                selected_group_ids=selected,
                server_id=service.server_id,
                for_edit=True,
                service_id=service.id,
            ).as_markup(),
        )

    client = Marzban.get_server(service.server_id)
    inbounds: dict[str, list[str]] = {
        protocol: [inbound.tag for inbound in protocol_inbounds]
        for protocol, protocol_inbounds in (
            await get_inbounds.asyncio(client=client)
        ).additional_properties.items()
    }
    await state.update_data(inbounds=service.inbounds)
    await query.message.edit_text(
        "اینباندها را انتخاب کنید و زخیره را کلیک کنید:",
        reply_markup=SelectInbounds(
            inbounds=inbounds,
            selected_inbounds=service.inbounds,
            server_id=service.server_id,
            for_edit=True,
            service_id=service.id,
        ).as_markup(),
    )


@router.callback_query(
    SelectServicesBulk.Callback.filter(),
    IsSuperUser(),
    StateFilter(EditServiceForm),
)
async def select_services_to_apply(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectServicesBulk.Callback,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    services = await Service.filter(
        id__not=callback_data.service_id, server_id=callback_data.server_id
    ).all()

    data = await state.get_data()
    selected: list[int] = data.get("apply_services", [])

    if callback_data.action == "all":
        selected = [service.id for service in services]
    elif callback_data.action == "none":
        selected = []
    else:
        if callback_data.sid in selected:
            selected.remove(callback_data.sid)
        else:
            selected.append(callback_data.sid)

    text = """
سرویس‌های مورد نظر را انتخاب کنید:
"""
    markup = SelectServicesBulk(
        service_id=callback_data.service_id,
        server_id=callback_data.server_id,
        services=services,
        selected=selected,
    ).as_markup()
    await state.update_data(apply_services=selected)
    try:
        return await query.message.edit_text(text=text, reply_markup=markup)
    except TelegramBadRequest:
        pass


@router.callback_query(
    EditServiceForm.inbounds,
    IsSuperUser(),
    SelectGroups.Callback.filter(F.for_edit == True),  # noqa: E712
)
@router.callback_query(
    AddServiceForm.inbounds,
    IsSuperUser(),
    SelectGroups.Callback.filter(F.for_edit == False),  # noqa: E712
)
async def select_service_groups(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectGroups.Callback,
):
    data = await state.get_data()
    selected: list[int] = list(data.get("group_ids", []))
    server = await Server.filter(id=callback_data.server_id).first()
    groups, err = await _fetch_panel_catalog(server, "groups") if server else (None, "❌ سرور یافت نشد.")
    if err is not None:
        return await query.answer(err, show_alert=True)
    if callback_data.group_id is not None:
        if callback_data.group_id in selected:
            selected.remove(callback_data.group_id)
        else:
            selected.append(callback_data.group_id)
        await state.update_data(group_ids=selected)

    markup = SelectGroups(
        groups=groups,
        selected_group_ids=selected,
        server_id=callback_data.server_id,
        for_edit=callback_data.for_edit,
        service_id=callback_data.service_id,
    ).as_markup()
    if not callback_data.for_edit:
        text = f"""
نام: <b>{data.get('name')}</b>
حجم: <b>{helpers.hr_size(data.get('data_limit')) if data.get('data_limit') else '♾'}</b>
اعتبار زمانی: <b>{helpers.hr_time(data.get('expire_duration')) if data.get('expire_duration') else '♾'}</b>
مبلغ: <b>{data.get('price')}</b>

گروه‌های انتخاب‌شده: <code>{selected}</code>
"""
        return await query.message.edit_text(text, reply_markup=markup)
    return await query.message.edit_reply_markup(reply_markup=markup)


@router.callback_query(
    EditServiceForm.inbounds,
    IsSuperUser(),
    SelectNodes.Callback.filter(F.for_edit == True),  # noqa: E712
)
@router.callback_query(
    AddServiceForm.inbounds,
    IsSuperUser(),
    SelectNodes.Callback.filter(F.for_edit == False),  # noqa: E712
)
async def select_service_nodes(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectNodes.Callback,
):
    data = await state.get_data()
    selected: list[int] = list(data.get("node_ids", []))
    server = await Server.filter(id=callback_data.server_id).first()
    nodes, err = await _fetch_panel_catalog(server, "nodes") if server else (None, "❌ سرور یافت نشد.")
    if err is not None:
        return await query.answer(err, show_alert=True)
    if callback_data.node_id is not None:
        if callback_data.node_id in selected:
            selected.remove(callback_data.node_id)
        else:
            selected.append(callback_data.node_id)
        await state.update_data(node_ids=selected)

    markup = SelectNodes(
        nodes=nodes,
        selected_node_ids=selected,
        server_id=callback_data.server_id,
        for_edit=callback_data.for_edit,
        service_id=callback_data.service_id,
    ).as_markup()
    if not callback_data.for_edit:
        text = f"""
نام: <b>{data.get('name')}</b>
حجم: <b>{helpers.hr_size(data.get('data_limit')) if data.get('data_limit') else '♾'}</b>
اعتبار زمانی: <b>{helpers.hr_time(data.get('expire_duration')) if data.get('expire_duration') else '♾'}</b>
مبلغ: <b>{data.get('price')}</b>

نودهای انتخاب‌شده: <code>{selected}</code>
"""
        return await query.message.edit_text(text, reply_markup=markup)
    return await query.message.edit_reply_markup(reply_markup=markup)


@router.callback_query(
    EditServiceForm.inbounds,
    IsSuperUser(),
    SelectInbounds.Callback.filter(F.for_edit == True),  # noqa: E712
)
@router.callback_query(
    AddServiceForm.inbounds,
    IsSuperUser(),
    SelectInbounds.Callback.filter(F.for_edit == False),  # noqa: E712
)
async def select_service_inbounds(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectInbounds.Callback,
):
    data = await state.get_data()
    selected_inbounds: dict[str, list[str]] = data.get("inbounds", dict())

    try:
        client = Marzban.get_server(callback_data.server_id)
    except KeyError:
        return await query.answer(
            text=f"خطایی در دریافت سرور {callback_data.server_id!r} رخ داد!"
        )
    inbounds: dict[str, list[str]] = {
        protocol: [inbound.tag for inbound in protocol_inbounds]
        for protocol, protocol_inbounds in (
            await get_inbounds.asyncio(client=client)
        ).additional_properties.items()
    }

    if callback_data.protocol is not None:
        if callback_data.inbound is None:
            if callback_data.protocol not in selected_inbounds:
                selected_inbounds.update(
                    {callback_data.protocol: inbounds[callback_data.protocol].copy()}
                )
            else:
                del selected_inbounds[callback_data.protocol]
        else:
            if callback_data.protocol not in selected_inbounds:
                selected_inbounds.update(
                    {callback_data.protocol: inbounds[callback_data.protocol].copy()}
                )
            else:
                if (
                    callback_data.inbound
                    not in selected_inbounds[callback_data.protocol]
                ):
                    selected_inbounds[callback_data.protocol].append(
                        callback_data.inbound
                    )
                else:
                    selected_inbounds[callback_data.protocol].remove(
                        callback_data.inbound
                    )
                    if not selected_inbounds[
                        callback_data.protocol
                    ]:  # delete protocol with no inbound
                        del selected_inbounds[callback_data.protocol]
        await state.update_data(inbounds=selected_inbounds)

    if not callback_data.for_edit:
        text = f"""
نام: <b>{data.get('name')}</b>
حجم: <b>{helpers.hr_size(data.get('data_limit')) if data.get('data_limit') else '♾'}</b>
اعتبار زمانی: <b>{helpers.hr_time(data.get('expire_duration')) if data.get('expire_duration') else '♾'}</b>
مبلغ: <b>{data.get('price')}</b>
سرور: <b>{data.get('server_id')}</b>

اینباندها: <code>{selected_inbounds}</code>
        """
        return await query.message.edit_text(
            text,
            reply_markup=SelectInbounds(
                inbounds=inbounds,
                selected_inbounds=selected_inbounds,
                server_id=callback_data.server_id,
            ).as_markup(),
        )
    text = f"""
اینباندها را انتخاب کنید و دکمه زخیره را کلیک کنید:

اینباندها:
<code>{json.dumps(selected_inbounds, indent=2)}</code>

"""
    if apply_services := data.get("apply_services"):
        ap_srv = [
            f"{service.id} - {service.display_name}\n"
            for service in await Service.filter(id__in=apply_services).all()
        ]
        text += f"""
تغییرات برای سرویس‌های زیر اعمال می‌شود:
{''.join(ap_srv)}

"""
    return await query.message.edit_text(
        text,
        reply_markup=SelectInbounds(
            inbounds=inbounds,
            selected_inbounds=selected_inbounds,
            server_id=callback_data.server_id,
            for_edit=True,
            service_id=callback_data.service_id,
        ).as_markup(),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.apply_inbounds_to_users),
    IsSuperUser(),
)
async def apply_inbounds_to_users(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if await redis.exists(f"bg_jobs:apply_inbounds:{service.id}"):
        return await query.answer(
            "یک عملیات از قبل در حال انجام است! لطفا تا اتمام عملیات قبلی منتظر بمانید."
        )

    if not callback_data.confirmed:
        await query.answer()
        text = """
مطمئن هستید که میخواهید اینباند‌ها برای تمام کاربران این سرویس ویرایش شود؟

تنظیماتی که بررسی و تغییر داده می‌شوند:
بازنشانی خودکار حجم
اینباندها
vless flow

(این عملیات ممکن است دقایقی طول بکشد)
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmServiceAction(
                service=service, action=ServiceActAction.apply_inbounds_to_users
            ).as_markup(),
        )

    await redis.setex(
        f"bg_jobs:apply_inbounds:{service.id}", 300, 1
    )  # deadlock defaults to 5 minutes
    users = await Proxy.filter(service_id=service.id).all()
    if not users:
        return await query.answer(
            "این سرویس کاربری برای ویرایش ندارد!",
            show_alert=True,
        )
    asyncio.create_task(
        proxy_management.bulk_update_users_inbounds(
            users=users,
            service=service,
            message=query.message,
            panel=get_panel(service.server_id),
        )
    )
    text = "♻️ عملیات در حال انجام است! نتیجه تا دقایقی دیگر برای شما ارسال می‌شود!"
    await query.answer(
        text=text,
        show_alert=True,
    )
    await query.message.edit_text(
        text=query.message.html_text + "\n\n" + text,
        reply_markup=ConfirmServiceAction(
            service=service, action=ServiceActAction.apply_inbounds_to_users
        ).as_markup(),
    )
    # return await show_services(query, user)


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.save_inbounds),
    IsSuperUser(),
    StateFilter(EditServiceForm),
)
async def edit_service_inbounds_save(
    query: CallbackQuery,
    user: User,
    callback_data: EditService.Callback,
    state: FSMContext,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    data = await state.get_data()
    try:
        del data["id"]
    except KeyError:
        pass
    if not data:
        return await query.answer(
            "تغییری ایجاد نشده است! دکمه لغو را کلیک کنید.", show_alert=True
        )

    server = await Server.filter(id=service.server_id).first()
    if server and _is_guardino(server):
        node_ids = data.get("node_ids", [])
        services_g: list[int] = data.get("apply_services", [])
        services_g.append(service.id)
        for s in await Service.filter(id__in=services_g):
            cfg = dict(s.panel_config or {})
            cfg["node_ids"] = node_ids
            cfg.setdefault("pricing_mode", "per_node")
            await Service.filter(id=s.id).update(panel_config=cfg)
        await state.clear()
        await query.answer("✅ ویرایش نودها انجام شد!", show_alert=True)
        return await show_service(
            query,
            user,
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
            state=None,
        )

    if server and _is_pasarguard(server):
        group_ids = data.get("group_ids")
        if not group_ids:
            return await query.answer("گروهی انتخاب نشده است!", show_alert=True)
        services_pg: list[int] = data.get("apply_services", [])
        services_pg.append(service.id)
        for s in await Service.filter(id__in=services_pg):
            cfg = dict(s.panel_config or {})
            cfg["group_ids"] = group_ids
            await Service.filter(id=s.id).update(panel_config=cfg)
        await state.clear()
        await query.answer("✅ ویرایش گروه‌ها انجام شد!", show_alert=True)
        return await show_service(
            query,
            user,
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
            state=None,
        )

    selected_inbounds: dict[str, list[str]] = data.get("inbounds", {})
    if not selected_inbounds:
        return await query.answer("پروتکلی انتخاب نشده است!", show_alert=True)

    if not any(
        [False if not inbounds else True for inbounds in selected_inbounds.values()]
    ):
        return await query.answer("اینباندی انتخاب نشده است!", show_alert=True)

    services: list[int] = data.get("apply_services", [])
    services.append(service.id)

    await Service.filter(id__in=services).update(inbounds=selected_inbounds)
    await state.clear()
    await query.answer("✅ ویرایش اینباند‌ها انجام شد!", show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
        state=None,
    )


@router.callback_query(
    AddServiceForm.inbounds,
    IsSuperUser(),
    Services.Callback.filter(F.action == ServicesAction.save_new),
)
async def save_new_service(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectInbounds.Callback,
):
    data = await state.get_data()
    server = await Server.filter(id=data.get("server_id")).first()

    if server and _is_guardino(server):
        node_ids = data.get("node_ids") or []
        await state.clear()
        await query.message.answer(
            "✅ سرویس ساخته شد!", reply_markup=ReplyKeyboardRemove()
        )
        service = await Service.create(
            name=data.get("name"),
            data_limit=data.get("data_limit"),
            expire_duration=data.get("expire_duration"),
            price=data.get("price"),
            inbounds={},  # Guardino provisions via panel_config (nodes/GB/days)
            panel_config={"node_ids": node_ids, "pricing_mode": "per_node"},
            server_id=data.get("server_id"),
        )
        return await show_service(
            query,
            user,
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
            state=state,
        )

    if server and _is_pasarguard(server):
        group_ids = data.get("group_ids") or []
        if not group_ids:
            return await query.answer("هیچ گروهی انتخاب نشده است!", show_alert=True)
        await state.clear()
        await query.message.answer(
            "✅ سرویس ساخته شد!", reply_markup=ReplyKeyboardRemove()
        )
        service = await Service.create(
            name=data.get("name"),
            data_limit=data.get("data_limit"),
            expire_duration=data.get("expire_duration"),
            price=data.get("price"),
            inbounds={},  # PasarGuard provisions via panel_config.group_ids
            panel_config={"group_ids": group_ids},
            server_id=data.get("server_id"),
        )
        return await show_service(
            query,
            user,
            callback_data=Services.Callback(
                service_id=service.id, action=ServicesAction.show
            ),
            state=state,
        )

    selected_inbounds: dict[str, list[str]] = data.get("inbounds")

    if not selected_inbounds:
        return await query.answer("هیچ پروتکلی انتخاب نشده است!", show_alert=True)

    if not any(
        [False if not inbounds else True for inbounds in selected_inbounds.values()]
    ):
        return await query.answer("هیچ اینباندی انتخاب نشده است!", show_alert=True)

    await state.clear()
    await query.message.answer("✅ سرویس ساخته شد!", reply_markup=ReplyKeyboardRemove())
    service = await Service.create(
        name=data.get("name"),
        data_limit=data.get("data_limit"),
        expire_duration=data.get("expire_duration"),
        price=data.get("price"),
        inbounds=selected_inbounds,
        server_id=data.get("server_id"),
    )
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
        state=state,
    )


# Show Services
@router.callback_query(
    IsSuperUser(),
    Services.Callback.filter(F.action == ServicesAction.show),
)
async def show_service(
    query: CallbackQuery,
    user: User,
    callback_data: Services.Callback,
    state: FSMContext | None = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    service = (
        await Service.filter(id=callback_data.service_id)
        .prefetch_related("server")
        .first()
    )
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if _is_guardino(service.server):
        cfg = service.panel_config or {}
        network_repr = (
            "نودها (Guardino): <code>"
            + json.dumps(cfg.get("node_ids", []))
            + f"</code>\nحالت قیمت: <code>{cfg.get('pricing_mode', 'per_node')}</code>"
            + f"\nسیاست لینک: <code>{getattr(service.server.link_policy, 'value', service.server.link_policy)}</code>"
        )
    elif _is_pasarguard(service.server):
        network_repr = (
            "گروه‌ها (PasarGuard): <code>"
            + json.dumps((service.panel_config or {}).get("group_ids", []))
            + "</code>"
        )
    else:
        network_repr = (
            "اینباندها: \n<code>" + json.dumps(service.inbounds, indent=2) + "</code>"
        )

    text = f"""
شناسه: <b>{service.id}</b>
نام: <b>{service.name}</b>
حجم: <b>{helpers.hr_size(service.data_limit)}</b>
اعتبار زمانی: <code>{helpers.hr_time(service.expire_duration)}</code>
مبلغ: <b>{service.price}</b>
سرور: <b>{service.server.name}</b> ({service.server.id})
{network_repr}

راهنما: https://t.me/c/2001448048/43
    """
    panel_type = getattr(
        service.server.panel_type, "value", service.server.panel_type
    )
    await query.message.edit_text(
        text,
        reply_markup=ServiceAct(service=service, panel_type=panel_type).as_markup(),
    )


# Remove Services
@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.rem),
    IsSuperUser(),
)
async def remove_service(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if not callback_data.confirmed:
        await query.answer()
        text = """
مطمئن هستید که میخواهید این سرویس را حذف کنید؟: 

❗️❗️<strong>این عمل برگشت ناپذیر است و سرویس از دسترس خارج می‌شود (اشتراک‌های خریداری شده حذف نمی‌شوند)</strong>
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmServiceAction(
                service=service, action=ServiceActAction.rem
            ).as_markup(),
        )
    await service.delete()
    await query.answer("سرویس با موفقیت حذف شد!", show_alert=True)
    return await show_services(query, user)


# update Services
@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.cycle_flow),
    IsSuperUser(),
)
async def service_cycle_flow(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    try:
        f = iter(Service.ServiceProxyFlow)
        while next(f) != service.flow:
            pass
        service.flow = next(f)
    except StopIteration:
        service.flow = next(iter(Service.ServiceProxyFlow))  # get first enum value

    await service.save()
    await query.answer(
        f"مقدار به {service.flow} تنظیم شد. فقط روی پروتکل‌هایی که 'flow' را پشتیبانی میکنند اعمال می‌شود!",
        show_alert=True,
    )
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_purchase),
    IsSuperUser(),
)
async def edit_service_purchase(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.purchaseable:
        service.purchaseable = False
        text = (
            "خرید سرویس غیرفعال شد! این سرویس در لیست خرید اشتراک نمایش داده نخواهد شد!"
        )
    else:
        service.purchaseable = True
        text = "خرید سرویس فعال شد! این سرویس در لیست خرید اشتراک نمایش داده می شود"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_renew),
    IsSuperUser(),
)
async def edit_service_renew(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if service.renewable:
        service.renewable = False
        text = "تمدید سرویس غیرفعال شد! این سرویس در لیست تمدید اشتراک نمایش داده نخواهد شد!"
    else:
        service.renewable = True
        text = (
            "تمدید سرویس فعال شد! این سرویس در لیست تمدید اشتراک نمایش داده خواهد شد!"
        )
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_one_time_only),
    IsSuperUser(),
)
async def edit_service_one_time_only(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("Service not found!", show_alert=True)
        return await show_services(query, user)
    if service.one_time_only:
        text = "خرید سرویس فقط یک بار غیرفعال شد! امکان خرید بیشتر از یک بار برای این سرویس فعال شد!"
        service.one_time_only = False
    else:
        service.one_time_only = True
        service.renewable = False
        text = "خرید سرویس فقط یک بار فعال شد! هر کاربر فقط یک بار می‌تواند این سرویس را خریداری کند"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_is_test_service),
    IsSuperUser(),
)
async def edit_service_is_test_service(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.is_test_service:
        service.is_test_service = False
        text = "سرویس از حالت سرویس تست خارج شد!"
    else:
        service.is_test_service = True
        service.renewable = False
        text = "سرویس به عنوان سرویس تست تنظیم شد!"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_create_on_hold_users),
    IsSuperUser(),
)
async def edit_service_create_on_hold_users(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if service.create_on_hold_users:
        service.create_on_hold_users = False
        text = "حالت شروع از اولین اتصال برای این سرویس غیرفعال شد!"
    else:
        service.create_on_hold_users = True
        text = "حالت شروع از اولین اتصال برای این سرویس فعال شد!"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.cycle_usage_reset_strategy),
    IsSuperUser(),
)
async def service_cycle_usage_reset_strategy(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    try:
        f = iter(Service.UsageResetStrategy)
        while next(f) != service.usage_reset_strategy:
            pass
        service.usage_reset_strategy = next(f)
    except StopIteration:
        service.usage_reset_strategy = next(
            iter(Service.UsageResetStrategy)
        )  # get first enum value

    await service.save()
    if service.usage_reset_strategy == service.UsageResetStrategy.no_reset:
        text = "بازنشانی خودکار حجم اشتراک‌ها برای این سرویس غیرفعال شد!"
    else:
        text = f"حجم مصرفی اشتراک‌های ساخته شده از این سرویس به صورت {USAGE_RESET_STRATEGY.get(service.usage_reset_strategy)} بازنشانی می‌شود! (فقط اشتراک‌های جدید)"
    await query.answer(
        text=text,
        show_alert=True,
    )
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(
        F.action == ServiceActAction.flip_append_available_data_renew
    ),
    IsSuperUser(),
)
async def edit_service__append_available_data_renew(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if service.append_available_data_renew:
        service.append_available_data_renew = False
        text = "ریست حجم باقیمانده هنگام تمدید برای این سرویس فعال شد!"
    else:
        service.append_available_data_renew = True
        text = "(حجم باقیمانده به دوره بعد اضافه می‌شود) ریست حجم باقیمانده هنگام تمدید برای این سرویس غیرفعال شد!"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.limits),
    IsSuperUser(),
)
async def edit_service_limits(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    text = """
در این قسمت می‌توانید مشخص کنید چه کاربرانی به این سرویس دسترسی خواهند داشت!

با فعال شدن «فقط کاربران مشخص شده» می‌توانید لیستی از کاربران را انتخاب کنید که سرویس فقط برای آن‌ها نمایش داده خواهد شد.
"""
    return await query.message.edit_text(
        text, reply_markup=ServiceActLimit(service=service).as_markup()
    )


@router.callback_query(
    ServiceActLimit.Callback.filter(F.action == ServiceActLimitAction.flip_users_only),
    IsSuperUser(),
)
async def edit_service_users_only(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.users_only:
        service.users_only = False
        text = "حالت «فقط کاربران معمولی» غیرفعال شد"
    else:
        service.users_only = True
        service.resellers_only = False
        service.user_filter = False
        text = "حالت «فقط کاربران معمولی» فعال شد و سرویس فقط به کاربران معمولی نمایش داده خواهد شد"
    await service.save()
    await query.answer(text, show_alert=True)
    await edit_service_limits(
        query,
        user,
        callback_data=ServiceAct.Callback(
            service_id=service.id, action=ServiceActAction.limits
        ),
    )


@router.callback_query(
    ServiceActLimit.Callback.filter(
        F.action == ServiceActLimitAction.flip_resellers_only
    ),
    IsSuperUser(),
)
async def edit_service_resellers_only(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.resellers_only:
        service.resellers_only = False
        text = "حالت «فقط فروشندگان» غیرفعال شد"
    else:
        service.resellers_only = True
        service.users_only = False
        service.user_filter = False
        text = (
            "حالت «فقط فروشندگان» فعال شد و سرویس فقط به فروشندگان نمایش داده خواهد شد"
        )
    await service.save()
    await query.answer(text, show_alert=True)
    await edit_service_limits(
        query,
        user,
        callback_data=ServiceAct.Callback(
            service_id=service.id, action=ServiceActAction.limits
        ),
    )


@router.callback_query(
    ServiceActLimit.Callback.filter(F.action == ServiceActLimitAction.flip_user_filter),
    IsSuperUser(),
)
async def edit_service_user_filter(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.user_filter:
        service.user_filter = False
        text = "حالت «فقط کاربران مشخص شده» غیرفعال شد"
    else:
        service.user_filter = True
        service.resellers_only = False
        service.users_only = False
        text = "حالت «فقط کاربران مشخص شده» فعال شد و سرویس فقط به کاربران انتخاب شده از لیست نمایش داده خواهد شد"
    await service.save()
    await query.answer(text, show_alert=True)
    await edit_service_limits(
        query,
        user,
        callback_data=ServiceAct.Callback(
            service_id=service.id, action=ServiceActAction.limits
        ),
    )


@router.callback_query(
    ServiceActLimit.Callback.filter(F.action == ServiceActLimitAction.select_users),
    IsSuperUser(),
)
@router.callback_query(
    ServiceActLimitUsers.Callback.filter(
        F.action == ServiceActLimitAction.select_users
    ),
    IsSuperUser(),
)
async def edit_service_select_users(
    query: CallbackQuery,
    user: User,
    callback_data: ServiceActLimit.Callback | ServiceActLimitUsers.Callback,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if isinstance(callback_data, ServiceActLimit.Callback):
        page = 0
    else:
        page = callback_data.current_page
        if callback_data.user_id:
            u = await User.filter(id=callback_data.user_id).first()
            if not u:
                return await query.answer("کاربر یافت نشد!")
            if await service.user_filters.filter(id=u.id).exists():
                await service.user_filters.remove(u)
            else:
                await service.user_filters.add(u)

    q = User.filter().order_by("-custom_name")
    total_count = await q.count()
    q = q.limit(11).offset(0 if page == 0 else page * 10)
    users = await q.all()
    selected_users = await service.user_filters.filter(
        id__in=[u.id for u in users]
    ).all()
    count = await q.count()

    reply_markup = ServiceActLimitUsers(
        service=service,
        users=users[:10],
        selected_users=[u.id for u in selected_users],
        current_page=page,
        count=total_count,
        next_page=True if count > 10 else False,
        prev_page=True if page > 0 else False,
    ).as_markup()
    start = 1 if page == 0 else (page * 10 + 1)
    end = 10 if page == 0 else ((start - 1) + (10 if count > 10 else count))
    selected_users_text = "\n".join(
        f"{user.custom_name if user.custom_name else user.name} ({f'@{user.username}' if user.username else user.id})"
    )
    text = f"""
این سرویس فقط به کاربرانی که علامت ✅ دارند نمایش داده خواهد شد!

برای انتخاب یا حذف هر کاربر روی آن کلیک کنید

کاربران انتخاب شده:
{selected_users_text}

🚦مشاهده: <b>{start}</b> تا <b>{end}</b> از <b>{total_count}</b>
    """
    return await query.message.edit_text(
        text=text,
        reply_markup=reply_markup,
    )


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.flip_all_inbounds),
    IsSuperUser(),
)
async def edit_service_all_inbounds(
    query: CallbackQuery, user: User, callback_data: ServiceAct.Callback
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    if service.all_inbounds:
        service.all_inbounds = False
        text = "حالت «ارسال همه اینباندها» غیرفعال شد و فقط اینباندهای انتخاب شده ارسال می‌شوند!"
    else:
        service.all_inbounds = True
        text = "حالت «ارسال همه اینباندها» فعال شد و همه اینباندها فعال می‌شوند!"
    await service.save()
    await query.answer(text, show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
    )


@router.message(
    F.text.casefold() == "cancel", IsSuperUser(), StateFilter(EditServiceForm)
)
@router.message(
    F.text.casefold() == CancelFormAdmin.cancel,
    StateFilter(EditServiceForm),
    IsSuperUser(),
)
@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.edit),
    IsSuperUser(),
)
async def edit_service(
    qmsg: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: ServiceAct.Callback = None,
):
    if callback_data:
        service_id = callback_data.service_id
    else:
        service_id = (await state.get_data()).get("id")
    service = await Service.filter(id=service_id).first()
    if not service:
        text = "سرویس یافت نشد!"
        if isinstance(qmsg, CallbackQuery):
            await qmsg.answer(text=text, show_alert=True)
            return await show_services(qmsg, user)
        else:
            return await qmsg.answer(text=text)

    await state.set_state(EditServiceForm.id)
    data = await state.get_data()
    unsaved_changes = []
    for key, value in data.items():
        if service.__dict__.get(key) != value:
            unsaved_changes.append(key)
    await state.update_data(id=service.id)
    inbs = service.inbounds if data.get("inbounds") is None else data.get("inbounds")
    text = f"""
تغییرات زخیره نشده: {'-' if not unsaved_changes else ', '.join(unsaved_changes)}

شناسه: <b>{service.id}</b>
نام: <b>{data.get('name') or service.name}</b>
حجم: <b>{helpers.hr_size(data.get('data_limit') or service.data_limit)}</b>
اعتبار زمانی: <code>{helpers.hr_time(data.get('expire_duration') or service.expire_duration)}</code>
مبلغ: <b>{data.get('price') or service.price}</b>
اینباندها:
 <code>{json.dumps(inbs, indent=2)}</code>
    """
    markup = EditService(service=service).as_markup()
    if isinstance(qmsg, Message):
        return await qmsg.answer(text, reply_markup=markup)
    return await qmsg.message.edit_text(text, reply_markup=markup)


@router.callback_query(
    EditService.Callback.filter(F.action == EditServiceAction.save),
    IsSuperUser(),
    StateFilter(EditServiceForm),
)
async def edit_service_save(
    query: CallbackQuery,
    user: User,
    callback_data: EditService.Callback,
    state: FSMContext,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)
    data = await state.get_data()
    del data["id"]
    if not data:
        return await query.answer(
            "تغییری ایجاد نشده است! دکمه لغو را کلیک کنید.", show_alert=True
        )

    # Only Marzban provisions via inbounds; PasarGuard/Guardino use panel_config,
    # so their services legitimately have empty inbounds — don't block the edit.
    server = await Server.filter(id=service.server_id).first()
    if not (server and (_is_pasarguard(server) or _is_guardino(server))):
        selected_inbounds: dict[str, list[str]] = (
            data.get("inbounds") or service.inbounds
        )
        if not selected_inbounds:
            return await query.answer("پروتکلی انتخاب نشده است!", show_alert=True)
        if not any(
            [False if not inbounds else True for inbounds in selected_inbounds.values()]
        ):
            return await query.answer("اینباندی انتخاب نشده است!", show_alert=True)

    await service.update_from_dict(data).save()
    await state.clear()
    await query.answer("فیلدهای ویرایش شده: " + ", ".join(data), show_alert=True)
    await show_service(
        query,
        user,
        callback_data=Services.Callback(
            service_id=service.id, action=ServicesAction.show
        ),
        state=None,
    )


@router.callback_query(
    EditService.Callback.filter(
        (F.action.in_(EditServiceAction)) & ~(F.action == EditServiceAction.save)
    ),
    IsSuperUser(),
)
async def edit_server_action(
    query: CallbackQuery,
    user: User,
    callback_data: EditService.Callback,
    state: FSMContext,
):
    service = await Service.filter(id=callback_data.service_id).first()
    if not service:
        await query.answer("سرویس یافت نشد!", show_alert=True)
        return await show_services(query, user)

    if callback_data.action == EditServiceAction.name:
        await state.set_state(EditServiceForm.name)
        await query.message.reply(
            "نام جدید سرویس را وارد کنید:", reply_markup=cancel_form
        )
    elif callback_data.action == EditServiceAction.data_limit:
        await state.set_state(EditServiceForm.data_limit)
        await query.message.reply(
            "مقدار حجم سرویس را به گیگابایت وارد کنید (برای نامحدود 0 را وارد کنید):",
            reply_markup=cancel_form,
        )
    elif callback_data.action == EditServiceAction.expire_duration:
        await state.set_state(EditServiceForm.expire_duration)
        text = """
مدت دوره زمانی جدید سرویس را به فرمت زیر وارد کنید:
^[0-9]{1,3}(D|M|Y|H)

مثال:
18h -> ۱۸ ساعت
3d -> سه روز
1m -> یک ماه
1y -> یک سال

(برای نامحدود 0 را وارد کنید)
"""
        await query.message.reply(text=text, reply_markup=cancel_form)
    elif callback_data.action == EditServiceAction.price:
        await state.set_state(EditServiceForm.price)
        await query.message.reply(
            "مبلغ جدید سرویس را وارد کنید:", reply_markup=cancel_form
        )


@router.message(
    EditServiceForm.name,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_name(message: Message, user: User, state: FSMContext):  # noqa: F811
    service_id = (await state.get_data()).get("id")
    service = await Service.filter(id=int(service_id)).first()
    if not service:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! دوباره تنظیمات را با دستور '/admin' باز کنید."
        )
    if service.name == message.text:
        return await message.answer(
            "نام جدید نمی‌تواند برابر با نام فعلی باشد! دوباره تلاش کنید:"
        )
    if await Service.filter(name=message.text).exists():
        return message.answer(
            "سرویس با این نام از قبل وجود دارد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(name=message.text)
    await edit_service(message, user, state)


@router.message(
    EditServiceForm.data_limit,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_data_limit(message: Message, user: User, state: FSMContext):  # noqa: F811
    service_id = (await state.get_data()).get("id")
    service = await Service.filter(id=int(service_id)).first()
    if not service:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! دوباره تنظیمات را با دستور '/admin' باز کنید."
        )
    try:
        if float(message.text) < 0:
            return await message.answer(
                message.chat.id,
                "❌ مقدار باید بیشتر یا مساوی 0 باشد",
                reply_markup=cancel_form(),
            )
        data_limit = float(message.text) * 1024 * 1024 * 1024
    except ValueError:
        return await message.answer(
            "مقدار باید عددی صحیح یا اعشاری باشد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    if service.data_limit == data_limit:
        return await message.answer(
            "مقدار جدید نمی‌تواند برابر با مقدار فعلی باشد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(data_limit=data_limit)
    await edit_service(message, user, state)


@router.message(
    EditServiceForm.expire_duration,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_expire_duration(message: Message, user: User, state: FSMContext):  # noqa: F811
    service_id = (await state.get_data()).get("id")
    service = await Service.filter(id=int(service_id)).first()
    if not service:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! دوباره تنظیمات را با دستور '/admin' باز کنید."
        )
    try:
        if message.text.isnumeric() and int(message.text) == 0:
            expire_duration = 0
        elif re.match(r"^[0-9]{1,3}(M|m|Y|y|D|d|H|h)$", message.text):
            expire_duration = 0
            number_pattern = r"^[0-9]{1,3}"
            number = int(re.findall(number_pattern, message.text)[0])
            symbol_pattern = r"(M|m|Y|y|D|d|H|h)$"
            symbol = re.findall(symbol_pattern, message.text)[0].upper()
            if symbol == "H":
                expire_duration = 3600 * number
            elif symbol == "D":
                expire_duration += 86400 * number
            elif symbol == "M":
                expire_duration += 2678400 * number
            elif symbol == "Y":
                expire_duration = 31104000 * number
        else:
            raise ValueError("خطایی در دریافت مدت زمان رخ داد! دوباره تلاش کنید:")
    except ValueError:
        return await message.answer(
            "❌ فرمت ارسالی نامعتبر است! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    server = await Server.filter(id=service.server_id).first()
    if server and _is_guardino(server) and 0 < expire_duration < 86400:
        return await message.answer(
            "❌ گاردینو مدت کمتر از ۱ روز را پشتیبانی نمی‌کند؛ حداقل ۱ روز (مثلاً 1d) وارد کنید:",
            reply_markup=cancel_form,
        )
    if service.expire_duration == expire_duration:
        return await message.answer(
            "مقدار جدید نمی‌تواند برابر با مقدار فعلی باشد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(expire_duration=expire_duration)
    await edit_service(message, user, state)


@router.message(
    EditServiceForm.price,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_service_price(message: Message, user: User, state: FSMContext):  # noqa: F811
    service_id = (await state.get_data()).get("id")
    service = await Service.filter(id=int(service_id)).first()
    if not service:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! دوباره تنظیمات را با دستور '/admin' باز کنید."
        )
    try:
        price = int(message.text)
    except ValueError:
        return await message.answer("مبلغ باید مقداری عددی باشد! دوباره تلاش کنید:")

    if service.price == price:
        return await message.answer(
            "مقدار جدید نمی‌تواند برابر با مقدار فعالی باشد! دوباره تلاش کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(price=price)
    await edit_service(message, user, state)


@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.broadcast), IsSuperUser()
)
async def broadcast_service(
    query: CallbackQuery | Message,
    user: User,
    callback_data: ServiceAct.Callback,
):
    text = f"""
برای ارسال یا فوروارد پیام همگانی به تمام کاربرانی که از این سرویس اشتراک دارند میتوانید از دستورات زیر استفاده کنید:

دستور را روی پیام مورد نظر ریپلی کنید!

پیام همگانی به تمام کاربران این سرویس:
<code>/broadcast srid={callback_data.service_id}</code>

فوروارد همگانی به تمام کاربران این سرویس:
<code>/forward srid={callback_data.service_id}</code>
"""
    await query.message.answer(text=text)


class ServiceBulkUpdateForm(StatesGroup):
    field = State()
    action = State()
    service_id = State()
    value = State()


@router.message(
    F.text.as_("msg_value"),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
    StateFilter(ServiceBulkUpdateForm),
)
@router.callback_query(
    ServiceAct.Callback.filter(F.action == ServiceActAction.bulk_update), IsSuperUser()
)
@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (
            ~F.proc.in_(
                [BulkUpdateProxiesProc.enter_value, BulkUpdateProxiesProc.proceed]
            )
        )
        & (F.category == "service")
    ),
    IsSuperUser(),
)
async def bulk_update_service_select(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateProxies.Callback | ServiceAct.Callback | None = None,
    state: FSMContext = None,
    msg_value: re.Match | None = None,
):
    field = action = value = service_id = None
    if isinstance(callback_data, BulkUpdateProxies.Callback):
        field, action, value, service_id = (
            callback_data.field,
            callback_data.action,
            callback_data.value,
            callback_data.service_id,
        )
        if (
            callback_data.proc == BulkUpdateProxiesProc.data_limit
            and field != "data_limit"
        ):
            field = "data_limit"
            value = None
        elif callback_data.proc == BulkUpdateProxiesProc.expire and field != "expire":
            field = "expire"
            value = None
        elif callback_data.proc == BulkUpdateProxiesProc.inc:
            action = "inc"
        elif callback_data.proc == BulkUpdateProxiesProc.dec:
            action = "dec"
    elif isinstance(callback_data, ServiceAct.Callback):
        service_id = callback_data.service_id
    else:
        if (
            (state is not None)
            and (await state.get_state() is not None)
            and msg_value is not None
        ):
            data = await state.get_data()
            field, action, service_id, value = (
                data.get("field"),
                data.get("action"),
                data.get("service_id"),
                data.get("value"),
            )
            if msg_value.casefold() == CancelFormAdmin.cancel:
                await state.clear()
                await qmsg.answer(
                    text="عملیات لغو شد!", reply_markup=ReplyKeyboardRemove()
                )
            else:
                try:
                    if field == "expire":
                        if (
                            match := re.match(
                                r"^([0-9]{1,3})\s?(M|m|Y|y|D|d|H|h)$", msg_value
                            )
                        ) is None:
                            raise ValueError()
                        number = int(match.group(1))
                        symbol = match.group(2).upper()
                        if symbol == "H":
                            value = 3600 * number
                        elif symbol == "D":
                            value = 86400 * number
                        elif symbol == "M":
                            value = 2678400 * number
                        elif symbol == "Y":
                            value = 31104000 * number
                        else:
                            raise ValueError()
                    else:
                        value = float(msg_value) * 1024 * 1024 * 1024
                except ValueError:
                    return await qmsg.answer(
                        "❌ فرمت ارسالی نامعتبر است! دوباره تلاش کنید:",
                        reply_markup=cancel_form,
                    )

    await state.update_data(
        field=field, action=action, service_id=service_id, value=value
    )
    text = "میخواهید کدام یک از مقادیر کاربر را تغییر دهید؟"
    if field == "data_limit":
        note = "\nنکته: اشتراک‌های منقضی شده، متوقف شده و غیرفعال ویرایش نخواهند شد!\n"
    elif field == "expire":
        note = "\nنکته: اشتراک‌های محدود شده، متوقف شده و غیرفعال ویرایش نخواهند شد!\n"
    else:
        note = ""
    proceed = False
    if value:
        text += f"""
\nمقدار وارد شده: {helpers.hr_time(value) if field == 'expire' else helpers.hr_size(value)}
سرویس انتخاب شده: {(await Service.filter(id=service_id).first()).display_name}
{note}
⚠️ اگر از اطلاعات وارد شده مطمئن هستید دکمه «اجرای دستور» را کلیک کنید!
"""
        proceed = True
    markup = BulkUpdateProxies(
        category="service",
        field=field,
        action=action,
        value=value,
        service_id=service_id,
        proceed_button=proceed,
    ).as_markup()
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(
                text=text,
                reply_markup=markup,
            )
        return await qmsg.answer(
            text=text,
            reply_markup=markup,
        )
    except TelegramBadRequest:
        pass


@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (F.proc == BulkUpdateProxiesProc.enter_value) & (F.category == "service")
    ),
    IsSuperUser(),
)
async def bulk_update_service_enter_value(
    query: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateProxies.Callback,
    state: FSMContext,
):
    if callback_data.field is None or callback_data.action is None:
        return await query.answer(
            "ابتدا اطلاعات خواسته شده را انتخاب کنید!", show_alert=True
        )

    _action = "افزایش" if callback_data.action == "inc" else "کاهش"
    if callback_data.field == "data_limit":
        text = f"""
برای {_action} حجم تمام اشتراک‌ها، مقدار مورد نظر را به گیگابایت وارد کنید
مثال: 
1
5
5.5
"""
    else:
        text = f"""
برای {_action} زمان تمام اشتراک‌ها، مقدار مورد نظر را به فرمت زیر وارد کنید
^[0-9]{1,3}(D|M|Y|H)

مثال:
18h -> ۱۸ ساعت
3d -> سه روز
1m -> یک ماه
1y -> یک سال
"""
    await state.set_state(ServiceBulkUpdateForm.value)
    await state.set_data(
        {
            "field": callback_data.field,
            "action": callback_data.action,
            "service_id": callback_data.service_id,
        }
    )
    await query.message.delete()
    await query.message.answer(text=text, reply_markup=cancel_form)


@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (F.proc == BulkUpdateProxiesProc.proceed) & (F.category == "service")
    ),
    IsSuperUser(),
)
async def bulk_update_service_proceed(
    query: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateProxies.Callback,
    state: FSMContext,
):
    if any(
        [
            callback_data.field is None,
            callback_data.action is None,
            callback_data.service_id is None,
            callback_data.value is None,
        ]
    ):
        return await query.answer(
            "ابتدا اطلاعات خواسته شده را انتخاب کنید!", show_alert=True
        )

    await query.answer("♻️ عملیات در حال اجرا می‌باشد لطفا منتظر بمانید...")

    _action = "افزایش" if callback_data.action == "inc" else "کاهش"
    _field = "حجم" if callback_data.field == "data_limit" else "زمان"
    q = Proxy.filter(service_id=callback_data.service_id)
    service = await Service.filter(id=callback_data.service_id).first()
    text = f"""
درحال {_action} مقدار {_field} برای تعداد {await q.count()} اشتراک

مقدار وارد شده: {helpers.hr_time(callback_data.value) if callback_data.field == 'expire' else helpers.hr_size(callback_data.value)}
سرویس انتخاب شده: {service.display_name}

عملیات در پشت صحنه انجام خواهد شد و نتیجه برای شما ارسال خواهد شد...
"""
    await query.message.edit_text(text=text)
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    proxies = await q.all()

    asyncio.create_task(
        proxy_management.bulk_update_users(
            users=proxies,
            field=callback_data.field,
            action=callback_data.action,
            by_value=callback_data.value,
            message=query.message,
            panel=get_panel(service.server_id),
        )
    )
