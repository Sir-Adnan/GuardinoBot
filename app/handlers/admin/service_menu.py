from aiogram import F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from tortoise.expressions import Q, RawSQL

from app.keyboards.admin.admin import (
    AdminPanel,
    AdminPanelAction,
    CancelFormAdmin,
    YesOrNoFormAdmin,
)
from app.keyboards.admin.service_menu import (
    MenuAction,
    Menues,
    MenuesConfirm,
    SelectServiceActions,
    SelectServices,
)
from app.models.service import Service, ServiceMenu
from app.models.user import User
from app.utils.filters import IsSuperUser

from . import router

cancel_form = CancelFormAdmin().as_markup(resize_keyboard=True, one_time_only=True)
yes_or_no_form = YesOrNoFormAdmin().as_markup(
    resize_keyboard=True, one_time_keyboard=True
)


class AddMenuForm(StatesGroup):
    parent_id = State()
    title = State()
    description = State()
    service_ids = State()
    user_ids = State()


class EditMenuForm(StatesGroup):
    menu_id = State()
    title = State()
    description = State()
    service_ids = State()


@router.message(
    F.text.casefold() == "cancel", IsSuperUser(), StateFilter(AddMenuForm, EditMenuForm)
)
@router.message(
    F.text == CancelFormAdmin.cancel,
    IsSuperUser(),
    StateFilter(AddMenuForm, EditMenuForm),
)
@router.message(
    Command("cancel"), IsSuperUser(), StateFilter(AddMenuForm, EditMenuForm)
)
@router.callback_query(
    AdminPanel.Callback.filter(F.action == AdminPanelAction.service_menues),
    IsSuperUser(),
)
@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.expand), IsSuperUser()
)
async def show_menues(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext | None = None,
    callback_data: Menues.Callback | None = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="Canceled!", reply_markup=ReplyKeyboardRemove())

    if isinstance(callback_data, Menues.Callback) and callback_data.menu_id:
        menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
        sub_menues = await ServiceMenu.filter(parent_id=menu.id).all()
        services = await menu.services.filter().all()
        text = f"""
نام زیرمنو: {menu.title}
توضیحات:
{menu.description if menu.description else '-'}
"""
    else:
        menu = None
        sub_menues = await ServiceMenu.filter(parent_id=None).all()
        # find services which dont belong to any menu
        services = await Service.filter(
            Q(
                id__not_in=RawSQL("(SELECT `service_id` FROM `services_to_menues`)"),
            )
        ).all()
        text = "لیست زیرمنو‌ها:\nراهنما: https://t.me/c/2001448048/49"

    markup = Menues(sub_menues=sub_menues, services=services, menu=menu).as_markup()
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text(
            text,
            reply_markup=markup,
        )
    return await query.answer(
        text,
        reply_markup=markup,
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.service_ph), IsSuperUser()
)
async def service_place_holder(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    await query.answer(
        "برای حذف یا اضافه کردن سرویس‌ها از دکمه «ویرایش سرویس‌ها» استفاده کنید!",
        show_alert=True,
    )


# create submenues
@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.add_sub_menu), IsSuperUser()
)
async def add_sub_menu(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    await state.set_state(AddMenuForm.title)
    await state.update_data(parent_id=callback_data.menu_id)
    await query.message.answer(
        "نامی برای زیرمنو انتخاب کنید:",
        reply_markup=cancel_form,
    )


@router.message(
    AddMenuForm.title,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_menu_name(message: Message, user: User, state: FSMContext):
    title = message.text.strip().replace("\n", " ")
    if await ServiceMenu.filter(title=title).first():
        return message.answer(
            "زیرمنویی با این نام از قبل وجود دارد! دوباره وارد کنید:",
            reply_markup=cancel_form,
        )
    await state.update_data(title=title)
    await state.set_state(AddMenuForm.description)
    await message.answer(
        "توضیحات این زیرمنو را وارد کنید (این متن در هنگام نمایش سرویس‌ها به کاربر نمایش داده میشود. برای عدم تنظیم 0 را وارد کنید):",
        reply_markup=cancel_form,
    )


@router.message(
    AddMenuForm.description,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_menu_description(message: Message, user: User, state: FSMContext):
    description = message.text.strip()
    if description == "0":
        description = None
    await state.update_data(description=description)
    await state.set_state(AddMenuForm.service_ids)
    services = await Service.all()
    markup = SelectServices(services=services, selected_services=[]).as_markup()
    await message.answer(
        "سرویس‌هایی که میخواهید در این زیرمنو نمایش داده شود را انتخاب کنید:",
        reply_markup=markup,
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.add_service), IsSuperUser()
)
async def edit_menu_services(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        await query.answer("not found!")

    services = await Service.all()
    selected_services = [service.id for service in await menu.services.filter().all()]
    markup = SelectServices(
        services=services,
        selected_services=selected_services,
        for_edit=True,
    ).as_markup()
    await state.set_state(EditMenuForm.service_ids)
    await state.update_data(menu_id=menu.id, service_ids=selected_services)
    await query.message.edit_text(
        "سرویس‌هایی که میخواهید در این زیرمنو نمایش داده شود را انتخاب کنید:",
        reply_markup=markup,
    )


@router.callback_query(
    StateFilter(EditMenuForm.service_ids, AddMenuForm.service_ids),
    SelectServices.Callback.filter(F.action == SelectServiceActions.toggle_selection),
    IsSuperUser(),
)
async def select_menu_services(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectServices.Callback,
):
    data = await state.get_data()
    selected_services: list[int] = data.get("service_ids", list())

    if callback_data.service_id in selected_services:
        selected_services.remove(callback_data.service_id)
    else:
        selected_services.append(callback_data.service_id)

    services = await Service.all()
    markup = SelectServices(
        services=services,
        selected_services=selected_services,
        for_edit=callback_data.for_edit,
    ).as_markup()

    await state.update_data(service_ids=selected_services)
    await query.message.edit_text(
        "سرویس‌هایی که میخواهید در این زیرمنو نمایش داده شود را انتخاب کنید:",
        reply_markup=markup,
    )


@router.callback_query(
    StateFilter(EditMenuForm.service_ids, AddMenuForm.service_ids),
    SelectServices.Callback.filter(F.action == SelectServiceActions.next),
    IsSuperUser(),
)
async def save_menu_services(
    query: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SelectServices.Callback,
):
    data = await state.get_data()
    service_ids = data.get("service_ids", [])
    if callback_data.for_edit:
        menu_id = data.get("menu_id")
        menu = await ServiceMenu.filter(id=menu_id).first()
        if not menu:
            return await query.answer("not found!")
        await menu.services.clear()
        services = await Service.filter(id__in=service_ids).all()
        if services:
            await menu.services.add(*services)

        await query.answer(
            "زیر منو با موفقیت ویرایش شد!",
            show_alert=True,
        )
        await state.clear()
        return await show_menues(
            query,
            user,
            state=None,
            callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
        )

    parent_id = data.get("parent_id", None)
    title = data.get("title")
    description = data.get("description", None)

    if parent_id:
        parent = await ServiceMenu.filter(id=parent_id).first()
    else:
        parent = None
    menu = await ServiceMenu.create(
        parent=parent,
        title=title,
        description=description,
    )
    services = await Service.filter(id__in=service_ids).all()
    if services:
        await menu.services.add(*services)

    await query.answer(
        "زیر منو با موفقیت ساخته شد!",
        show_alert=True,
    )
    await state.clear()
    await show_menues(
        query,
        user,
        state=None,
        callback_data=Menues.Callback(menu_id=parent_id, action=MenuAction.expand),
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.toggle_resellers_only), IsSuperUser()
)
async def toggle_resellers_only(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        return await query.answer("not found!")

    if menu.resellers_only:
        menu.resellers_only = False
        text = "نمایش برای فقط فروشنده‌ها غیرفعال شد!"
    else:
        menu.resellers_only = True
        menu.users_only = False
        text = "نمایش برای فقط فروشنده‌ها غیرفعال شد!"
    await menu.save()
    await query.answer(text, show_alert=True)
    return await show_menues(
        query,
        user,
        state=None,
        callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.toggle_users_only), IsSuperUser()
)
async def toggle_users_only(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        return await query.answer("not found!")

    if menu.users_only:
        menu.users_only = False
        text = "نمایش برای فقط کاربران معمولی غیرفعال شد!"
    else:
        menu.users_only = True
        menu.resellers_only = False
        text = "نمایش برای فقط کاربران معمولی غیرفعال شد!"
    await menu.save()
    await query.answer(text, show_alert=True)
    return await show_menues(
        query,
        user,
        state=None,
        callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.toggle_purchase), IsSuperUser()
)
async def toggle_purchase(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        return await query.answer("not found!")

    if menu.purchase:
        menu.purchase = False
        text = "نمایش در لیست خرید غیرفعال شد!"
    else:
        menu.purchase = True
        text = "نمایش در لیست خرید غیرفعال شد!"
    await menu.save()
    await query.answer(text, show_alert=True)
    return await show_menues(
        query,
        user,
        state=None,
        callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.toggle_renew), IsSuperUser()
)
async def toggle_renew(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        return await query.answer("not found!")

    if menu.renew:
        menu.renew = False
        text = "نمایش در لیست تمدید غیرفعال شد!"
    else:
        menu.renew = True
        text = "نمایش در لیست تمدید غیرفعال شد!"
    await menu.save()
    await query.answer(text, show_alert=True)
    return await show_menues(
        query,
        user,
        state=None,
        callback_data=Menues.Callback(menu_id=menu.id, action=MenuAction.expand),
    )


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.delete), IsSuperUser()
)
async def delete_menu(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    menu = await ServiceMenu.filter(id=callback_data.menu_id).first()
    if not menu:
        return await query.answer("not found!")

    if callback_data.confirmed:
        parent_id = menu.parent_id
        await menu.delete()
        await query.answer("زیر منو حذف شد!", show_alert=True)
        return await show_menues(
            query,
            user,
            state=None,
            callback_data=Menues.Callback(
                menu_id=parent_id if parent_id else 0, action=MenuAction.expand
            ),
        )

    markup = MenuesConfirm(menu=menu, action=MenuAction.delete).as_markup()
    return await query.message.edit_text(
        "مطمئن هستید که میخواهید این زیرمنو حذف شود؟", reply_markup=markup
    )


# edit submenues
@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.edit_title), IsSuperUser()
)
async def edit_title(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    await state.set_state(EditMenuForm.title)
    await state.update_data(menu_id=callback_data.menu_id)
    await query.message.answer(
        "نامی برای زیرمنو انتخاب کنید:",
        reply_markup=cancel_form,
    )


@router.message(
    EditMenuForm.title,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_title_get(message: Message, user: User, state: FSMContext):
    title = message.text.strip().replace("\n", " ")
    if await ServiceMenu.filter(title=title).first():
        return message.answer(
            "زیرمنویی با این نام از قبل وجود دارد! دوباره وارد کنید:",
            reply_markup=cancel_form,
        )
    data = await state.get_data()
    menu_id = data.get("menu_id")
    if menu_id:
        if await ServiceMenu.filter(id=menu_id).update(title=title):
            await state.clear()
            await message.answer("نام زیرمنو ویرایش شد!")
            return await show_menues(
                message,
                user,
                state=None,
                callback_data=Menues.Callback(
                    menu_id=menu_id, action=MenuAction.expand
                ),
            )
    await message.answer("خطایی رخ داد!")


@router.callback_query(
    Menues.Callback.filter(F.action == MenuAction.edit_description), IsSuperUser()
)
async def edit_description(
    query: CallbackQuery | Message,
    user: User,
    state: FSMContext,
    callback_data: Menues.Callback,
):
    await state.set_state(EditMenuForm.description)
    await state.update_data(menu_id=callback_data.menu_id)
    await query.message.answer(
        "توضیحات زیرمنو را وارد کنید:",
        reply_markup=cancel_form,
    )


@router.message(
    EditMenuForm.description,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def edit_description_get(message: Message, user: User, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    menu_id = data.get("menu_id")
    if menu_id:
        if await ServiceMenu.filter(id=menu_id).update(description=description):
            await state.clear()
            await message.answer("توضیحات زیرمنو ویرایش شد!")
            return await show_menues(
                message,
                user,
                state=None,
                callback_data=Menues.Callback(
                    menu_id=menu_id, action=MenuAction.expand
                ),
            )
    await message.answer("خطایی رخ داد!")
