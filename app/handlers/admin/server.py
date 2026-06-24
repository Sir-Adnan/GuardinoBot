import asyncio
import re

import httpx
from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.filters.command import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from tortoise.expressions import F as TF

from app.keyboards.admin.admin import (
    AdminPanel,
    AdminPanelAction,
    BulkUpdateProxies,
    BulkUpdateProxiesProc,
    CancelFormAdmin,
    YesOrNoFormAdmin,
)
from app.keyboards.admin.server import (
    BulkUpdateServices,
    BulkUpdateServicesProc,
    ConfirmServerAction,
    EditServer,
    EditServerAction,
    ServerAct,
    ServerActAction,
    Servers,
    ServersAction,
)
from app.marzban import Marzban
from app.panels import PanelRegistry, PanelType, get_panel
from app.panels.base import PanelAuthError, PanelError
from app.panels.guardino import login as guardino_login
from app.panels.guardino import validate as guardino_validate
from app.models.proxy import Proxy
from app.models.server import LinkPolicy, Server
from app.models.service import Service
from app.models.user import User
from app.utils import helpers, proxy_management
from app.utils.filters import IsSubscriptionURL, IsSuperUser
from marzban_client import AuthenticatedClient, Client
from marzban_client.api.admin import admin_token, get_current_admin
from marzban_client.errors import UnexpectedStatus
from marzban_client.models.body_admin_token_api_admin_token_post import (
    BodyAdminTokenApiAdminTokenPost,
)

from . import router

cancel_form = CancelFormAdmin().as_markup(resize_keyboard=True, one_time_only=True)
yes_or_no_form = YesOrNoFormAdmin().as_markup(
    resize_keyboard=True, one_time_keyboard=True
)
panel_type_form = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Marzban"), KeyboardButton(text="PasarGuard")],
        [KeyboardButton(text="Guardino")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)
link_policy_form = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="مستر گاردینو"), KeyboardButton(text="لینک نود")]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


class AddServerForm(StatesGroup):
    panel_type = State()
    name = State()
    host = State()
    port = State()
    https = State()
    token = State()
    guardino_creds = State()  # Guardino: reseller username/password
    link_policy = State()  # Guardino: which sub link to show
    username = State()
    password = State()
    confirm = State()


class EditServerForm(StatesGroup):
    id = State()
    name = State()
    host = State()
    port = State()
    token = State()
    https = State()


@router.message(
    F.text.casefold() == CancelFormAdmin.cancel,
    IsSuperUser(),
    StateFilter(AddServerForm, EditServerForm),
)
@router.message(
    Command("cancel"), IsSuperUser(), StateFilter(AddServerForm, EditServerForm)
)
@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.servers), IsSuperUser()
)
async def show_servers(
    query: CallbackQuery | Message, user: User, state: FSMContext | None = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="Canceled!", reply_markup=ReplyKeyboardRemove())
    count = await Server.all().count()
    if count:
        text = f"لیست سرورها ({count}):"
        markup = Servers(servers=await Server.all()).as_markup()
    else:
        text = "سروری اضافه نشده است!"
        markup = Servers(servers=[]).as_markup()

    text += "\nراهنما: https://t.me/c/2001448048/32"
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text(text=text, reply_markup=markup)
    return await query.answer(text=text, reply_markup=markup)


@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.ping), IsSuperUser()
)
async def ping_servers(
    query: CallbackQuery | Message,
    user: User,
    callback_data: ServerAct.Callback,
):
    try:
        panel = get_panel(callback_data.server_id)
        admin = await panel.get_admin()
        text = f"""
اتصال به سرور موفقیت آمیز بود!
نام کاربری: {admin.username}
سودو: {'✅' if admin.is_sudo else '❌'}
            """
        return await query.answer(text=text, show_alert=True)
    except PanelAuthError:
        return await query.answer(
            "خطای احراز هویت در اتصال به پنل! اعتبارنامه تنظیم‌شده را بررسی کنید",
            show_alert=True,
        )
    except PanelError as exc:
        return await query.answer(
            text="امکان اتصال به سرور وجود ندارد! آدرس/پورت/اعتبارنامه را بررسی کنید\n"
            + str(exc),
            show_alert=True,
        )
    except Exception as exc:
        await query.answer(
            text="خطای ناشناخته در اتصال به سرور!\n" + str(exc),
            show_alert=True,
        )
        raise exc


# Add Servers
@router.callback_query(
    Servers.Callback.filter(F.action == ServersAction.add_server),
    IsSuperUser(),
)
async def add_server(query: CallbackQuery, user: User, state: FSMContext):
    await state.set_state(AddServerForm.panel_type)
    await query.message.answer(
        "نوع پنل این سرور را انتخاب کنید:",
        reply_markup=panel_type_form,
    )


@router.message(
    AddServerForm.panel_type,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_panel_type(message: Message, user: User, state: FSMContext):
    choice = (message.text or "").strip().lower()
    if choice in ("pasarguard", "پاسارگارد", "pasar guard"):
        panel_type = PanelType.pasarguard.value
    elif choice in ("guardino", "گاردینو", "guardino hub", "گاردینو هاب"):
        panel_type = PanelType.guardino.value
    elif choice in ("marzban", "مرزبان"):
        panel_type = PanelType.marzban.value
    else:
        return await message.answer(
            "لطفا یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=panel_type_form,
        )
    await state.update_data(panel_type=panel_type)
    await state.set_state(AddServerForm.name)
    await message.answer(
        "نامی برای سرور انتخاب کنید:",
        reply_markup=cancel_form,
    )


@router.message(
    AddServerForm.name,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_name(message: Message, user: User, state: FSMContext):
    if await Server.filter(name=message.text).first():
        return message.answer(
            "سروری با نام مورد نظر از قبل اضافه شده است. دوباره وارد کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(name=message.text)
    await state.set_state(AddServerForm.host)
    await message.answer(
        "دامنه یا آی پی سرور را وارد کنید:",
        reply_markup=cancel_form,
    )


@router.message(
    AddServerForm.host,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_host(message: Message, user: User, state: FSMContext):
    # TODO: validate address
    await state.update_data(host=message.text)
    await state.set_state(AddServerForm.port)
    await message.answer(
        "پورت سرور مورد نظر را وارد کنید: (برای استفاده نکردن از پورت 0 را وارد کنید)",
        reply_markup=cancel_form,
    )


@router.message(
    AddServerForm.port,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_port(message: Message, user: User, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer(
            "پورت باید مقداری عددی باشد! دوباره وارد کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(port=int(message.text))
    await state.set_state(AddServerForm.https)
    await message.answer(
        "سرور مورد نظر از https استفاده می‌کند؟", reply_markup=yes_or_no_form
    )


TOKEN_TEXT = """
توکن سرور یا یوزرنیم و پسوورد سرور را به فرمت زیر وارد کنید (هر کدام در یک خط):

<blockquote>
username
password
</blockquote>"""
TOKEN_VALIDATION_ERR_TEXT = f"""
فرمت ارسالی نادرست است!

{TOKEN_TEXT}"""


@router.message(
    AddServerForm.https,
    IsSuperUser(),
    F.text.casefold().in_(["بله", "خیر"]),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_https_yes_or_no(message: Message, user: User, state: FSMContext):
    if message.text.casefold() == "خیر":
        await state.update_data(https=False)
    else:
        await state.update_data(https=True)

    data = await state.get_data()
    if data.get("panel_type") == PanelType.guardino.value:
        # Guardino connects with reseller username/password (login), not a token.
        await state.set_state(AddServerForm.guardino_creds)
        return await message.answer(text=GUARDINO_CREDS_TEXT, reply_markup=cancel_form)

    await state.set_state(AddServerForm.token)
    await message.answer(text=TOKEN_TEXT, reply_markup=cancel_form)


@router.message(
    AddServerForm.https,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_https_unknown(message: Message, user: User, state: FSMContext):
    await message.answer(
        text="جواب نامشخص! لطفا یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=yes_or_no_form,
    )


GUARDINO_CREDS_TEXT = """
یوزرنیم و پسوورد رسلر (یا سوپرادمین) گاردینو هاب را وارد کنید (هر کدام در یک خط):

<blockquote>
username
password
</blockquote>

⚠️ حساب ربات باید 2FA غیرفعال داشته باشد."""


def _build_server_url(data: dict) -> str:
    url = "https://" if data.get("https", False) else "http://"
    url += data["host"]
    if data.get("port"):
        url += f":{data['port']}"
    return url


@router.message(
    AddServerForm.guardino_creds,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_guardino_creds(message: Message, user: User, state: FSMContext):
    data = await state.get_data()
    url = _build_server_url(data)
    try:
        username, password = message.text.split("\n")
        username, password = username.strip(), password.strip()
    except ValueError:
        return await message.answer(GUARDINO_CREDS_TEXT, reply_markup=cancel_form)

    try:
        token_resp = await guardino_login(url, username, password)
    except PanelAuthError:
        return await message.answer(
            "خطا در احراز هویت گاردینو هاب! یوزرنیم/پسوورد را بررسی کنید.",
            reply_markup=cancel_form,
        )
    except PanelError as exc:
        await message.answer(
            "امکان اتصال به گاردینو هاب نبود! آدرس/پورت را بررسی کنید.\n" + str(exc),
            reply_markup=cancel_form,
        )
        raise exc

    if token_resp.get("requires_2fa"):
        return await message.answer(
            "حساب گاردینو 2FA فعال دارد. لطفا 2FA را غیرفعال کنید یا از حسابی بدون 2FA استفاده کنید.",
            reply_markup=cancel_form,
        )
    access_token = token_resp.get("access_token")
    if not access_token:
        return await message.answer(
            "توکنی از گاردینو هاب دریافت نشد!", reply_markup=cancel_form
        )

    try:
        admin = await guardino_validate(url, access_token)
    except PanelAuthError:
        return await message.answer(
            "اعتبارسنجی توکن گاردینو ناموفق بود!", reply_markup=cancel_form
        )

    me = admin.raw or {}
    await state.update_data(username=username, password=password, token=access_token)
    await state.set_state(AddServerForm.link_policy)
    balance = me.get("balance")
    text = (
        "✅ اتصال به گاردینو هاب موفق بود!\n"
        f"کاربر: {admin.username}\n"
        f"نقش: {me.get('role', '-')}\n"
        f"موجودی: {balance if balance is not None else '-'} تومان\n\n"
        "سیاست نمایش لینک اشتراک به کاربر را انتخاب کنید:\n"
        "• «مستر گاردینو»: لینک مرکزی هاب (در صورت روشن بودن)\n"
        "• «لینک نود»: لینک پنل زیرین (PasarGuard/WireGuard)"
    )
    await message.answer(text, reply_markup=link_policy_form)


@router.message(
    AddServerForm.link_policy,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_link_policy(message: Message, user: User, state: FSMContext):
    choice = (message.text or "").strip().lower()
    if choice in ("مستر گاردینو", "مستر", "master", "master_first"):
        policy = LinkPolicy.master_first.value
    elif choice in ("لینک نود", "نود", "node", "node_first"):
        policy = LinkPolicy.node_first.value
    else:
        return await message.answer(
            "لطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=link_policy_form
        )
    await state.update_data(link_policy=policy)
    data = await state.get_data()
    await state.set_state(AddServerForm.confirm)
    await message.answer(
        "اطلاعات زیر صحیح است؟\n"
        f"نام سرور: {data['name']}\n"
        f"آدرس: {_build_server_url(data)}\n"
        "پنل: Guardino Hub\n"
        f"سیاست لینک: {'مستر گاردینو' if policy == LinkPolicy.master_first.value else 'لینک نود'}\n",
        reply_markup=yes_or_no_form,
    )


class GetTokenError(Exception):
    pass


async def get_token_from_username_password(url: str, username: str, password: str):
    try:
        resp = await admin_token.asyncio(
            client=Client(url, raise_on_unexpected_status=True),
            body=BodyAdminTokenApiAdminTokenPost(
                username=username.strip(), password=password.strip()
            ),
        )
    except UnexpectedStatus as exc:
        if exc.status_code == 401:
            raise GetTokenError("خطا در احراز هویت از سمت سرور!")
    if resp is None:
        raise GetTokenError("جوابی از سمت سرور دریافت نشد!")
    if isinstance(resp, admin_token.HTTPValidationError):
        raise GetTokenError(
            f"خطای برگشتی از پنل: {resp.detail}\n\n{TOKEN_VALIDATION_ERR_TEXT}"
        )
    return resp.access_token


@router.message(
    AddServerForm.token,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_token_handler(message: Message, user: User, state: FSMContext):
    data = await state.get_data()

    # login to server
    if data.get("https", False):
        url = "https://"
    else:
        url = "http://"
    url += data["host"]
    if (port := data.get("port", None)) is not None:
        url += f":{port}"

    try:
        token = await IsSubscriptionURL()(message)
        if not token:
            try:
                username, password = message.text.split("\n")
            except ValueError:
                return await message.answer(TOKEN_VALIDATION_ERR_TEXT)
            try:
                access_token = await get_token_from_username_password(
                    url, username, password
                )
            except GetTokenError as exc:
                return await message.answer(text=str(exc), reply_markup=cancel_form)
            await state.update_data(username=username, password=password)
        else:
            access_token = token.get("token")

        client = AuthenticatedClient(
            url, token=access_token, raise_on_unexpected_status=True
        )
        resp = await get_current_admin.asyncio_detailed(client=client)
        if resp.status_code == 200:
            text = f"""
اتصال به سرور موفقیت آمیز بود! 
نام کاربری: {resp.parsed.username}
سودو: {'✅' if resp.parsed.is_sudo else '❌'}
            """
            await state.update_data(token=access_token)
            await state.set_state(AddServerForm.confirm)
            await message.answer(
                text=text,
            )
            return await message.answer(
                "اطلاعات زیر صحیح است؟?\n"
                f"نام سرور: {data['name']}\n"
                f"آدرس: {url}\n",
                reply_markup=yes_or_no_form,
            )
    except UnexpectedStatus as exc:
        if exc.status_code == 401:
            text = f"خطای احراز هویت در اتصال به پنل! توکن یا یوزرنیم/پسوورد ارسال شده را بررسی کنید\n\n{TOKEN_VALIDATION_ERR_TEXT}"
        else:
            text = f"خطای ناشناخته در اتصال به سرور: {exc.status_code}: {exc.content.decode()}"
        await message.answer(text=text, reply_markup=cancel_form)
        raise exc
    except httpx.ConnectError as exc:
        await message.answer(
            text="امکان اتصال به سرور وجود ندارد! آدرس و پورت سرور را بررسی کنید",
            reply_markup=cancel_form,
        )
        raise exc
    except Exception as exc:
        await message.answer(
            text="خطای ناشناخته در اتصال به سرور!\n" + str(exc),
            reply_markup=cancel_form,
        )
        raise exc


@router.message(
    AddServerForm.confirm,
    IsSuperUser(),
    F.text.casefold() == "بله",
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_confirm_yes(message: Message, user: User, state: FSMContext):
    data = await state.get_data()
    server = await Server.create(**data)

    await message.reply(
        f"سرور اضافه شد:\nidentifier: {server.identifier}\nurl: {server.url}"
    )
    await Marzban.refresh_servers()
    await PanelRegistry.refresh()
    await show_servers(message, user)


@router.message(
    AddServerForm.confirm,
    IsSuperUser(),
    F.text.casefold() == "خیر",
    ~CommandStart(),
    ~Command("menu"),
)
async def get_server_confirm_no(message: Message, user: User, state: FSMContext):
    await state.set_state(AddServerForm.name)
    await message.answer(
        "دوباره وارد کنید!\nنامی برای سرور مورد نظر انتخاب کنید:",
        reply_markup=cancel_form,
    )


# Show Servers
@router.callback_query(
    Servers.Callback.filter(F.action == ServersAction.show), IsSuperUser()
)
async def show_server(
    query: CallbackQuery,
    user: User,
    callback_data: Servers.Callback,
    state: FSMContext = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        await query.answer("سرور یافت نشد!", show_alert=True)
        return await show_servers(
            query,
            user,
        )

    text = f"""
شناسه سرور: <b>{server.id}</b>
نام سرور: <b>{server.name}</b>
آدرس سرور: <b>{server.url}</b>
وضعیت: <b>{'✅ فعال' if server.is_enabled else '❌ غیرفعال'}</b>


شمارنده اشتراک‌ها: <code>{server.total_proxies}</code>

راهنما: https://t.me/c/2001448048/37
    """
    await query.message.edit_text(
        text, reply_markup=ServerAct(server).as_markup(), disable_web_page_preview=True
    )


# Remove Servers
@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.rem),
    IsSuperUser(),
)
async def remove_server(
    query: CallbackQuery, user: User, callback_data: ServerAct.Callback
):
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        await query.answer("سرور یافت نشد!", show_alert=True)
        return await show_servers(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        text = """
سرور پاک شود؟: 

❗️❗️<strong>این عمل دائمی می‌باشد و اطلاعات تمام پروکسی‌ها پاک می شود! می‌توانید به جای حذف سرور را غیرفعال کنید تا برای فروش/تمدید نمایش داده نشود.</strong>
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmServerAction(
                server=server, action=ServerActAction.rem
            ).as_markup(),
        )
    await server.delete()
    await query.answer("سرور حذف شد!", show_alert=True)
    return await show_servers(
        query,
        user,
    )


# Update Servers
@router.callback_query(
    ServerAct.Callback.filter(
        (F.action == ServerActAction.enable) | (F.action == ServerActAction.disable)
    ),
    IsSuperUser(),
)
async def server_status_update(
    query: CallbackQuery, user: User, callback_data: ServerAct.Callback
):
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        await query.answer("سرور یافت نشد!", show_alert=True)
        return await show_servers(
            query,
            user,
        )

    if callback_data.action == ServerActAction.disable:
        if not server.is_enabled:
            await query.answer("سرور فعال نیست!", show_alert=True)
            return await show_server(
                query,
                user,
                callback_data=Servers.Callback(server_id=server.id, action="show"),
            )
        if not callback_data.confirmed:
            await query.answer()
            return await query.message.edit_text(
                "سرور غیرفعال شود؟",
                reply_markup=ConfirmServerAction(
                    server=server, action=ServerActAction.disable
                ).as_markup(),
            )
        server.is_enabled = False
        await server.save()
        await query.answer("سرور غیرفعال شد!", show_alert=True)
    elif callback_data.action == ServerActAction.enable:
        if server.is_enabled:
            await query.answer("سرور غیرفعال نیست!", show_alert=True)
            return await show_server(
                query,
                user,
                callback_data=Servers.Callback(server_id=server.id, action="show"),
            )
        if not callback_data.confirmed:
            await query.answer()
            return await query.message.edit_text(
                "سرور فعال شود؟",
                reply_markup=ConfirmServerAction(
                    server=server, action=ServerActAction.enable
                ).as_markup(),
            )
        server.is_enabled = True
        await server.save()
        await query.answer("سرور فعال شد", show_alert=True)
    return await show_server(
        query,
        user,
        callback_data=Servers.Callback(server_id=server.id, action="show"),
    )


@router.message(F.text.casefold() == "لغو", IsSuperUser(), StateFilter(EditServerForm))
@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.edit),
    IsSuperUser(),
)
async def edit_server(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: ServerAct.Callback = None,
):
    if callback_data:
        server_id = callback_data.server_id
    else:
        server_id = (await state.get_data()).get("id")
    server = await Server.filter(id=server_id).first()
    if not server:
        if isinstance(query, CallbackQuery):
            await query.answer("سرور یافت نشد!", show_alert=True)
            return await show_servers(
                query,
                user,
            )
        else:
            return await query.answer("سرور یافت نشد!")

    await state.set_state(EditServerForm.id)
    data = await state.get_data()
    unsaved_changes = []
    for key, value in data.items():
        if server.__dict__.get(key) != value:
            unsaved_changes.append(key)
    await state.update_data(id=server.id)
    text = f"""
تغییرات ذخیره نشده: {'-' if not unsaved_changes else ', '.join(unsaved_changes)}

شناسه سرور: <b>{server.id}</b>
نام سرور: <b>{data.get('name') or server.name}</b>
هاست سرور: <b>{data.get('host') or server.host}</b>
پورت سرور: <b>{data.get('port') or server.port}</b>
https: <b>{server.https if data.get('https') is None else data.get('https')}</b>
وضعیت: <b>{'✅ فعال' if server.is_enabled else '❌ غیرفعال'}</b>

server token: <code>{data.get('token') or server.token}</code>
    """
    markup = EditServer(server=server).as_markup()
    if isinstance(query, Message):
        return await query.answer(text, reply_markup=markup)
    return await query.message.edit_text(text, reply_markup=markup)


@router.callback_query(
    EditServer.Callback.filter(F.action == EditServerAction.save),
    IsSuperUser(),
    StateFilter(EditServerForm),
)
async def edit_server_save(
    query: CallbackQuery,
    user: User,
    callback_data: EditServer.Callback,
    state: FSMContext,
):
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        await query.answer("سرور یافت نشد!", show_alert=True)
        return await show_servers(
            query,
            user,
        )
    data = await state.get_data()
    del data["id"]
    if not data:
        return await query.answer(
            "چیزی را تغییر نداده‌اید! برای لغو از دکمه لغو استفاده کنید.",
            show_alert=True,
        )
    await Server.filter(id=server.id).update(**data)
    await state.clear()
    await query.answer(
        "بروزرسانی انجام شد! بروز شده‌ها: " + ", ".join(data), show_alert=True
    )
    await Marzban.refresh_servers()
    await PanelRegistry.refresh()
    await show_server(
        query,
        user,
        callback_data=Servers.Callback(server_id=server.id, action=ServersAction.show),
        state=None,
    )


@router.callback_query(
    EditServer.Callback.filter(
        (F.action.in_(EditServerAction)) & ~(F.action == EditServerAction.save)
    ),
    IsSuperUser(),
)
async def edit_server_action(
    query: CallbackQuery,
    user: User,
    callback_data: EditServer.Callback,
    state: FSMContext,
):
    server = await Server.filter(id=callback_data.server_id).first()
    if not server:
        await query.answer("سرور یافت نشد!", show_alert=True)
        return await show_servers(
            query,
            user,
        )

    if callback_data.action == EditServerAction.name:
        await state.set_state(EditServerForm.name)
        await query.message.reply(
            "نام جدید سرور را وارد کنید:",
            reply_markup=cancel_form,
        )
    elif callback_data.action == EditServerAction.host:
        await state.set_state(EditServerForm.host)
        await query.message.reply(
            "دامنه یا آی پی جدید سرور را وارد کنید:",
            reply_markup=cancel_form,
        )
    elif callback_data.action == EditServerAction.port:
        await state.set_state(EditServerForm.port)
        await query.message.reply(
            "پورت جدید سرور را وارد کنید (برای استفاده نکردن از پورت 0 را وارد کنید):",
            reply_markup=cancel_form,
        )
    elif callback_data.action == EditServerAction.token:
        await state.set_state(EditServerForm.token)
        await query.message.reply(TOKEN_TEXT, reply_markup=cancel_form)
    elif callback_data.action == EditServerAction.https:
        https = (await state.get_data()).get("https") or server.https
        if https:
            await state.update_data(https=False)
        else:
            await state.update_data(https=True)
        await edit_server(query, user, state)


@router.message(
    EditServerForm.name,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_server_name(message: Message, user: User, state: FSMContext):
    server_id = (await state.get_data()).get("id")
    server = await Server.filter(id=int(server_id)).first()
    if not server:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! با دستور /admin دوباره تنظیمات را باز کنید"
        )
    if server.name == message.text:
        return await message.answer(
            "نام جدید نمی‌تواند با قدیمی برابر باشد. دوباره وارد کنید یا دکمه لغو را بزنید:"
        )

    if await Server.filter(name=message.text).exists():
        return message.answer(
            "سروری با نام مورد نظر از قبل اضافه شده‌است! دوباره وارد کنید:",
            reply_markup=cancel_form,
        )

    await state.update_data(name=message.text)
    await edit_server(message, user, state)


@router.message(
    EditServerForm.host,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_server_host(message: Message, user: User, state: FSMContext):
    server_id = (await state.get_data()).get("id")
    server = await Server.filter(id=int(server_id)).first()
    if not server:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! با دستور /admin دوباره تنظیمات را باز کنید"
        )
    if server.host == message.text:
        return await message.answer(
            "دامنه یا آی پی جدید نمی‌تواند با قدیمی برابر باشد! دوباره وارد کنید یا دکمه لغو را بزنید:"
        )
    await state.update_data(host=message.text)
    await edit_server(message, user, state)


@router.message(
    EditServerForm.port,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_server_port(message: Message, user: User, state: FSMContext):
    server_id = (await state.get_data()).get("id")
    server = await Server.filter(id=int(server_id)).first()
    if not server:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! با دستور /admin دوباره تنظیمات را باز کنید"
        )
    if not message.text.isdigit():
        return await message.answer(
            "پورت باید مقداری عددی باشد! دوباره وارد کنید::",
            reply_markup=cancel_form,
        )
    if server.port == int(message.text):
        return await message.answer(
            "پورت جدید نمی‌تواند با پورت قدیمی برابر باشد! دوباره وارد کنید یا دکمه لغو را بزنید:"
        )
    await state.update_data(port=int(message.text))
    await edit_server(message, user, state)


@router.message(
    EditServerForm.token,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_server_token(message: Message, user: User, state: FSMContext):
    server_id = (await state.get_data()).get("id")
    server = await Server.filter(id=int(server_id)).first()
    if not server:
        await state.clear()
        return await message.answer(
            "خطایی رخ داد! با دستور /admin دوباره تنظیمات را باز کنید"
        )

    try:
        token = await IsSubscriptionURL()(message)
        if not token:
            try:
                username, password = message.text.split("\n")
            except ValueError:
                return await message.answer(TOKEN_VALIDATION_ERR_TEXT)

            try:
                access_token = await get_token_from_username_password(
                    server.url, username, password
                )
            except GetTokenError as exc:
                return await message.answer(text=str(exc), reply_markup=cancel_form)
            await state.update_data(username=username, password=password)
        else:
            access_token = token.get("token")

        client = AuthenticatedClient(
            server.url, token=access_token, raise_on_unexpected_status=True
        )
        resp = await get_current_admin.asyncio_detailed(client=client)
        if resp.status_code == 200:
            text = f"""
اتصال به سرور موفقیت آمیز بود! 
نام کاربری: {resp.parsed.username}
سودو: {'✅' if resp.parsed.is_sudo else '❌'}
            """
            if server.token == message.text:
                return await message.answer(
                    "توکن جدید نمی‌تواند با توکن قدیمی برابر باشد! دوباره وارد کنید یا دکمه لغو را بزنید:"
                )
            await state.update_data(token=access_token)
            return await edit_server(message, user, state)
    except UnexpectedStatus as exc:
        if exc.status_code == 401:
            text = f"خطای احراز هویت در اتصال به پنل! توکن یا یوزرنیم/پسوورد ارسال شده را بررسی کنید\n\n{TOKEN_VALIDATION_ERR_TEXT}"
        else:
            text = f"خطای ناشناخته در اتصال به سرور: {exc.status_code}: {exc.content.decode()}"
        await message.answer(text=text, reply_markup=cancel_form)
        raise exc
    except httpx.ConnectError as exc:
        await message.answer(
            text="امکان اتصال به سرور وجود ندارد! آدرس و پورت سرور را بررسی کنید",
            reply_markup=cancel_form,
        )
        raise exc
    except Exception as exc:
        await message.answer(
            text="خطای ناشناخته در اتصال به سرور!\n" + str(exc),
            reply_markup=cancel_form,
        )
        raise exc


@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.broadcast), IsSuperUser()
)
async def broadcast_server(
    query: CallbackQuery | Message,
    user: User,
    callback_data: ServerAct.Callback,
):
    text = f"""
برای ارسال یا فوروارد پیام همگانی به تمام کاربرانی که از این سرور اشتراک دارند میتوانید از دستورات زیر استفاده کنید:

دستور را روی پیام مورد نظر ریپلی کنید!

پیام همگانی به تمام کاربران این سرور:
<code>/broadcast svid={callback_data.server_id}</code>

فوروارد همگانی به تمام کاربران این سرور:
<code>/forward svid={callback_data.server_id}</code>
"""
    await query.message.answer(text=text)


class ServerBulkUpdateForm(StatesGroup):
    field = State()
    action = State()
    server_id = State()
    value = State()


@router.message(
    F.text.as_("msg_value"),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
    StateFilter(ServerBulkUpdateForm),
)
@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.bulk_update), IsSuperUser()
)
@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (
            ~F.proc.in_(
                [BulkUpdateProxiesProc.enter_value, BulkUpdateProxiesProc.proceed]
            )
        )
        & (F.category == "server")
    ),
    IsSuperUser(),
)
async def bulk_update_server_select(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateProxies.Callback | ServerAct.Callback | None = None,
    state: FSMContext = None,
    msg_value: re.Match | None = None,
):
    field = action = value = server_id = None
    if isinstance(callback_data, BulkUpdateProxies.Callback):
        field, action, value, server_id = (
            callback_data.field,
            callback_data.action,
            callback_data.value,
            callback_data.server_id,
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
    elif isinstance(callback_data, ServerAct.Callback):
        server_id = callback_data.server_id
    else:
        if (
            (state is not None)
            and (await state.get_state() is not None)
            and msg_value is not None
        ):
            data = await state.get_data()
            field, action, server_id, value = (
                data.get("field"),
                data.get("action"),
                data.get("server_id"),
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
                            value = 2592000 * number
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
        field=field, action=action, server_id=server_id, value=value
    )
    text = "میخواهید کدام یک از مقادیر کاربر را تغییر دهید؟"
    if field == "data_limit":
        note = "\nنکته: اشتراک‌های منقضی شده، در اتنظار اولین اتصال و غیرفعال ویرایش نخواهند شد!\n"
    elif field == "expire":
        note = "\nنکته: اشتراک‌های محدود شده، در اتنظار اولین اتصال و غیرفعال ویرایش نخواهند شد!\n"
    else:
        note = ""
    proceed = False
    if value:
        text += f"""
\nمقدار وارد شده: {helpers.hr_time(value) if field == 'expire' else helpers.hr_size(value)}
سرور انتخاب شده: {(await Server.filter(id=server_id).first()).identifier}
{note}
⚠️ اگر از اطلاعات وارد شده مطمئن هستید دکمه «اجرای دستور» را کلیک کنید!
"""
        proceed = True
    markup = BulkUpdateProxies(
        category="server",
        field=field,
        action=action,
        value=value,
        server_id=server_id,
        proceed_button=proceed,
    ).as_markup()
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text=text, reply_markup=markup)
        return await qmsg.answer(text=text, reply_markup=markup)
    except TelegramBadRequest:
        pass


@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (F.proc == BulkUpdateProxiesProc.enter_value) & (F.category == "server")
    ),
    IsSuperUser(),
)
async def bulk_update_server_enter_value(
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
    await state.set_state(ServerBulkUpdateForm.value)
    await state.set_data(
        {
            "field": callback_data.field,
            "action": callback_data.action,
            "server_id": callback_data.server_id,
        }
    )
    await query.message.delete()
    await query.message.answer(text=text, reply_markup=cancel_form)


@router.callback_query(
    BulkUpdateProxies.Callback.filter(
        (F.proc == BulkUpdateProxiesProc.proceed) & (F.category == "server")
    ),
    IsSuperUser(),
)
async def bulk_update_server_proceed(
    query: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateProxies.Callback,
    state: FSMContext,
):
    if any(
        [
            callback_data.field is None,
            callback_data.action is None,
            callback_data.server_id is None,
            callback_data.value is None,
        ]
    ):
        return await query.answer(
            "ابتدا اطلاعات خواسته شده را انتخاب کنید!", show_alert=True
        )

    await query.answer("♻️ عملیات در حال اجرا می‌باشد لطفا منتظر بمانید...")

    _action = "افزایش" if callback_data.action == "inc" else "کاهش"
    _field = "حجم" if callback_data.field == "data_limit" else "زمان"
    q = Proxy.filter(server_id=callback_data.server_id)
    server = await Server.filter(id=callback_data.server_id).first()
    text = f"""
درحال {_action} مقدار {_field} برای تعداد {await q.count()} اشتراک

مقدار وارد شده: {helpers.hr_time(callback_data.value) if callback_data.field == 'expire' else helpers.hr_size(callback_data.value)}
سرور انتخاب شده: {server.identifier}

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
            panel=get_panel(server.id),
        )
    )


class BulkUpdateFormServices(StatesGroup):
    field = State()
    action = State()
    server_id = State()
    value = State()


@router.message(
    F.text.as_("msg_value"),
    ~CommandStart(),
    ~Command("menu"),
    IsSuperUser(),
    StateFilter(BulkUpdateFormServices),
)
@router.callback_query(
    ServerAct.Callback.filter(F.action == ServerActAction.change_price), IsSuperUser()
)
@router.callback_query(
    BulkUpdateServices.Callback.filter(
        ~F.proc.in_(
            [BulkUpdateServicesProc.enter_value, BulkUpdateServicesProc.proceed]
        )
    ),
    IsSuperUser(),
)
async def bulk_update_services_select(
    qmsg: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateServices.Callback | ServerAct.Callback | None = None,
    state: FSMContext = None,
    msg_value: re.Match | None = None,
):
    field = action = value = server_id = None
    if isinstance(callback_data, BulkUpdateServices.Callback):
        field, action, value, server_id = (
            callback_data.field,
            callback_data.action,
            callback_data.value,
            callback_data.server_id,
        )
        if callback_data.proc == BulkUpdateServicesProc.percent and field != "percent":
            field = "percent"
            value = None
        elif callback_data.proc == BulkUpdateServicesProc.toman and field != "toman":
            field = "toman"
            value = None
        elif callback_data.proc == BulkUpdateServicesProc.inc:
            action = "inc"
        elif callback_data.proc == BulkUpdateServicesProc.dec:
            action = "dec"
    elif isinstance(callback_data, ServerAct.Callback):
        server_id = callback_data.server_id
    else:
        if (
            (state is not None)
            and (await state.get_state() is not None)
            and msg_value is not None
        ):
            data = await state.get_data()
            field, action, server_id, value = (
                data.get("field"),
                data.get("action"),
                data.get("server_id"),
                data.get("value"),
            )
            if msg_value.casefold() == CancelFormAdmin.cancel:
                await state.clear()
                await qmsg.answer(
                    text="عملیات لغو شد!", reply_markup=ReplyKeyboardRemove()
                )
            else:
                try:
                    value = float(msg_value)
                except ValueError:
                    return await qmsg.answer(
                        "❌ فرمت ارسالی نامعتبر است! دوباره تلاش کنید:",
                        reply_markup=cancel_form,
                    )

    await state.update_data(
        field=field, action=action, server_id=server_id, value=value
    )
    text = "میخواهید قیمت سرویس‌ها به شکل تغییر کند؟"
    proceed = False
    if value:
        svs_text = [
            f"{service.display_name}\n"
            for service in await Service.filter(server_id=server_id).all()
        ]
        text += f"""
\nمقدار وارد شده: {value} {'درصد' if field == 'percent' else 'تومان'}
سرویس‌های انتخاب شده: 

{''.join(svs_text)}

⚠️ اگر از اطلاعات وارد شده مطمئن هستید دکمه «اجرای دستور» را کلیک کنید!
"""
        proceed = True
    markup = BulkUpdateServices(
        field=field,
        action=action,
        value=value,
        server_id=server_id,
        proceed_button=proceed,
    ).as_markup()
    try:
        if isinstance(qmsg, CallbackQuery):
            return await qmsg.message.edit_text(text=text, reply_markup=markup)
        return await qmsg.answer(text=text, reply_markup=markup)
    except TelegramBadRequest:
        pass


@router.callback_query(
    BulkUpdateServices.Callback.filter(F.proc == BulkUpdateServicesProc.enter_value),
    IsSuperUser(),
)
async def bulk_update_services_enter_value(
    query: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateServices.Callback,
    state: FSMContext,
):
    if callback_data.field is None or callback_data.action is None:
        return await query.answer(
            "ابتدا اطلاعات خواسته شده را انتخاب کنید!", show_alert=True
        )

    _action = "افزایش" if callback_data.action == "inc" else "کاهش"
    if callback_data.field == "percent":
        text = f"""
چند درصد {_action} قیمت روی سرویس‌های انتخاب شده اعمال شود؟
"""
    else:
        text = f"""
مبلغ مورد نظر برای {_action} قیمت سرویس‌های انتخاب شده را به تومان وارد کنید:
"""
    await state.set_state(BulkUpdateFormServices.value)
    await state.set_data(
        {
            "field": callback_data.field,
            "action": callback_data.action,
            "server_id": callback_data.server_id,
        }
    )
    await query.message.delete()
    await query.message.answer(text=text, reply_markup=cancel_form)


@router.callback_query(
    BulkUpdateServices.Callback.filter(F.proc == BulkUpdateServicesProc.proceed),
    IsSuperUser(),
)
async def bulk_update_services_proceed(
    query: CallbackQuery | Message,
    user: User,
    callback_data: BulkUpdateServices.Callback,
    state: FSMContext,
):
    if any(
        [
            callback_data.field is None,
            callback_data.action is None,
            callback_data.server_id is None,
            callback_data.value is None,
        ]
    ):
        return await query.answer(
            "ابتدا اطلاعات خواسته شده را انتخاب کنید!", show_alert=True
        )

    await query.answer("♻️ عملیات در حال اجرا می‌باشد لطفا منتظر بمانید...")

    _action = "افزایش" if callback_data.action == "inc" else "کاهش"

    q = Service.filter(server_id=callback_data.server_id)
    if callback_data.field == "percent":
        if callback_data.action == "inc":
            q = q.update(price=TF("price") * ((callback_data.value / 100) + 1))
        else:
            q = q.update(price=TF("price") * (1 - (callback_data.value / 100)))
        _field = "درصد"
    else:
        if callback_data.action == "inc":
            q = q.update(price=TF("price") + callback_data.value)
        else:
            q = q.update(price=TF("price") - callback_data.value)
        _field = "تومان"

    await q
    svs_text = [
        f"{service.display_name}\n"
        for service in await Service.filter(server_id=callback_data.server_id).all()
    ]
    text = f"""
{_action} قیمت {callback_data.value} {_field} برای سرویس‌های زیر اعمال شد

{''.join(svs_text)}
"""
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    await query.message.answer(text=text)
    return await show_server(
        query,
        user,
        callback_data=Servers.Callback(
            server_id=callback_data.server_id, action="show"
        ),
    )
