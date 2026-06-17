import re
from datetime import datetime as dt
from datetime import timedelta as td

from aiogram import F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.keyboards.admin.admin import CancelFormAdmin, YesOrNoFormAdmin
from app.keyboards.admin.discount import (
    ConfirmDiscountAction,
    DiscountAct,
    DiscountActAction,
    Discounts,
    DiscountsAction,
    SelectServices,
)
from app.keyboards.admin.service import Services, ServicesAction
from app.main import get_bot_username
from app.models.service import Discount, Service
from app.models.user import User
from app.utils import helpers
from app.utils.filters import IsSuperUser

from . import router

cancel_form = CancelFormAdmin().as_markup(resize_keyboard=True, one_time_only=True)
yes_or_no_form = YesOrNoFormAdmin().as_markup(
    resize_keyboard=True, one_time_keyboard=True
)


class AddDiscountForm(StatesGroup):
    percentage = State()
    expires_at = State()
    use_counts = State()
    code = State()
    service_ids = State()


class EditDiscountForm(StatesGroup):
    id = State()
    percentage = State()
    expires_at = State()
    service_ids = State()


@router.message(F.text.casefold() == "لغو", IsSuperUser(), StateFilter(AddDiscountForm))
@router.message(Command("cancel"), IsSuperUser(), StateFilter(AddDiscountForm))
@router.callback_query(
    Services.Callback.filter(F.action == ServicesAction.discounts), IsSuperUser()
)
async def show_discounts(
    query: CallbackQuery | Message, user: User, state: FSMContext | None = None
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
        await query.answer(text="عملیات لغو شد!", reply_markup=ReplyKeyboardRemove())
    count = await Discount.all().count()
    if count:
        discounts = Discounts(discounts=await Discount.all()).as_markup()
        if isinstance(query, CallbackQuery):
            return await query.message.edit_text(
                f"لیست تخفیفات ({count}):",
                reply_markup=discounts,
            )
        return await query.answer(
            f"لیست تخفیفات ({count}):",
            reply_markup=discounts,
        )
    discounts = Discounts(discounts=[]).as_markup()
    if isinstance(query, CallbackQuery):
        return await query.message.edit_text(
            "تخفیفی اضافه نشده است!", reply_markup=discounts
        )
    return await query.answer("تخفیفی اضافه نشده است!", reply_markup=discounts)


# add discounts
@router.callback_query(
    Discounts.Callback.filter(F.action == DiscountsAction.add),
    IsSuperUser(),
)
async def add_discount(query: CallbackQuery, user: User, state: FSMContext):
    await state.set_state(AddDiscountForm.percentage)
    await query.message.answer(
        "درصد تخفیف را وارد کنید (بین 1 - 100):",
        reply_markup=cancel_form,
    )


@router.message(
    AddDiscountForm.percentage,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_discount_percentage(message: Message, user: User, state: FSMContext):
    percent = message.text
    try:
        percent = int(percent)
    except ValueError:
        return message.reply(f"{percent} ورودی نامعتر است! عددی بین ۱ تا ۱۰۰ وارد کنید")
    if percent > 100 or percent < 1:
        return message.reply(f"{percent} ورودی نامعتر است! عددی بین ۱ تا ۱۰۰ وارد کنید")
    await state.update_data(percentage=percent)
    await state.set_state(AddDiscountForm.expires_at)
    await message.answer(
        "⬆️ مدت زمان اعتبار را وارد کنید:\n"
        "'^[0-9]{1,3}(D|M|Y|H)' :\n"
        "(D: روز, M: ماه, Y: سال, H: ساعت)\n"
        "⚠️ برای منقضی نشدن 0 را وارد کنید\n"
        "<code>(1d = ۱ روز)</code>",
        reply_markup=cancel_form,
    )


@router.message(
    AddDiscountForm.expires_at,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_discount_expires_at(message: Message, user: User, state: FSMContext):
    try:
        if message.text.isnumeric() and int(message.text) == 0:
            expires_at = None
        elif re.match(r"^[0-9]{1,3}(M|m|Y|y|D|d|H|h)$", message.text):
            expires_at = 0
            number_pattern = r"^[0-9]{1,3}"
            number = int(re.findall(number_pattern, message.text)[0])
            symbol_pattern = r"(M|m|Y|y|D|d|H|h)$"
            symbol = re.findall(symbol_pattern, message.text)[0].upper()
            if symbol == "H":
                expires_at = 3600 * number
            elif symbol == "D":
                expires_at += 86400 * number
            elif symbol == "M":
                expires_at += 2592000 * number
            elif symbol == "Y":
                expires_at = 31104000 * number
        else:
            raise ValueError("Could not parse expires_at")
    except ValueError:
        return await message.answer(
            "❌  فرمت ورودی باید به شکل "
            "1m or 2m or 1d باشد!\n"
            "\n Regex Symbol: ^[0-9]{1,3}(D|M|Y|H)",
            reply_markup=cancel_form,
        )
    await state.update_data(expires_at=expires_at)
    await state.set_state(AddDiscountForm.use_counts)
    data = await state.get_data()
    if expires_at:
        expires_at = dt.now() + td(seconds=expires_at)
    await message.answer(
        f"درصد: {data.get('percentage')}\n"
        f"انقضا: {helpers.hr_date(expires_at.timestamp()) if expires_at else '♾'}\n\n"
        "تعداد دفعاتی که این تخفیف قابلیت استفاده دارد را وارد کنید (برای نامحدود بودن 0 را وارد کنید)",
        reply_markup=cancel_form,
    )


@router.message(
    AddDiscountForm.use_counts,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_discount_use_counts(message: Message, user: User, state: FSMContext):
    count = message.text
    try:
        count = int(count)
    except ValueError:
        return message.reply(
            f"{count} ورودی نامعتر است! عددی بیشتر یا مساوی 0 وارد کنید"
        )

    await state.update_data(use_counts=count)
    await state.set_state(AddDiscountForm.code)
    data = await state.get_data()
    if (expires_at := data.get("expires_at")) is not None:
        expires_at = dt.now() + td(seconds=expires_at)
    await message.answer(
        f"درصد: {data.get('percentage')}\n"
        f"انقضا: {helpers.hr_date(expires_at.timestamp()) if expires_at else '♾'}\n"
        f"محدودیت استفاده: {data.get('use_counts') if data.get('use_counts') else '♾'}\n\n"
        "کد تخفیف را وارد کنید: (بین ۴ تا ۳۲ کاراکتر و فقط اعداد و حروف انگلیسی)\n\n"
        "(برای ساخته شدن رندوم کد r را وارد کنید. و برای عدم تنظیم کد تخفیف 0 را وارد کنید.)\n"
        "اگر کدی تنظیم نشود، تخفیف برای تمام کاربران اعمال می‌شود!",
        reply_markup=cancel_form,
    )


@router.message(
    AddDiscountForm.code,
    IsSuperUser(),
    ~CommandStart(),
    ~Command("menu"),
)
async def get_discount_code(message: Message, user: User, state: FSMContext):
    code = message.text
    if code == "0":
        code = None
    elif code == "r":
        code = Discount.generate_code()
        if await Discount.filter(code=code).exists():
            code = Discount.generate_code()
    else:
        if not (3 < len(code) <= 32):
            return await message.reply(
                "کد تخفیف باید بین ۳ تا ۳۲ کاراکتر و فقط اعداد و حروف انگلیسی باشد! دوباره وارد کنید:"
            )
        if not code.isalnum():
            return await message.reply(
                "کد تخفیف باید بین ۳ تا ۳۲ کاراکتر و فقط اعداد و حروف انگلیسی باشد! دوباره وارد کنید:"
            )
        if code[0].isnumeric():
            return await message.reply(
                "کد تخفیف حتما باید با یک حرف انگلیسی شروع شود! دوباره وارد کنید:"
            )
        if await Discount.filter(code=code).exists():
            return await message.reply(
                "تخفیفی با این کد قبلا ساخته شده است! دوباره وارد کنید:"
            )

    await state.update_data(code=code)
    await state.set_state(AddDiscountForm.service_ids)
    data = await state.get_data()
    if (expires_at := data.get("expires_at")) is not None:
        expires_at = dt.now() + td(seconds=expires_at)
    await message.answer(
        f"درصد: {data.get('percentage')}\n"
        f"انقضا: {helpers.hr_date(expires_at.timestamp()) if expires_at else '♾'}\n"
        f"محدودیت استفاده: {data.get('use_counts') if data.get('use_counts') else '♾'}\n"
        f"کد تخفیف: <code>{data.get('code') if data.get('code') else '➖'}</code>\n\n"
        "روی چه سرویس‌هایی اعمال شود؟\n"
        "(این تخفیف بر تخفیف‌های قبلی سرویس اولویت خواهد داشت! و اگر سرویسی انتخاب نشود روی همه سرویس‌ها اعمال می‌شود)",
        reply_markup=SelectServices(
            services=await Service.all(), selected_services=[]
        ).as_markup(),
    )


@router.callback_query(
    AddDiscountForm.service_ids, IsSuperUser(), SelectServices.Callback.filter()
)
async def select_server_ids(
    query: CallbackQuery,
    user: User,
    callback_data: SelectServices.Callback,
    state: FSMContext,
):
    data = await state.get_data()
    selected_services: list[int] = data.get("service_ids", [])
    if callback_data.service_id in selected_services:
        selected_services.remove(callback_data.service_id)
    else:
        selected_services.append(callback_data.service_id)

    await state.update_data(service_ids=selected_services)
    expires_at = data.get("expires_at")
    if expires_at:
        expires_at = dt.now() + td(seconds=expires_at)
    await query.message.edit_text(
        f"درصد: {data.get('percentage')}\n"
        f"انقضا: {helpers.hr_date(expires_at.timestamp()) if expires_at else '♾'}\n"
        f"محدودیت استفاده: {data.get('use_counts') if data.get('use_counts') else '♾'}\n"
        f"کد تخفیف: <code>{data.get('code') if data.get('code') else '➖'}</code>\n\n"
        "روی چه سرویس‌هایی اعمال شود؟\n"
        "(این تخفیف بر تخفیف‌های قبلی سرویس اولویت خواهد داشت! و اگر سرویسی انتخاب نشود روی همه سرویس‌ها اعمال می‌شود)",
        reply_markup=SelectServices(
            services=await Service.all(), selected_services=selected_services
        ).as_markup(),
    )


@router.callback_query(
    StateFilter(AddDiscountForm),
    IsSuperUser(),
    Discounts.Callback.filter(F.action == DiscountsAction.save_new),
)
async def save_discount(query: CallbackQuery, user: User, state: FSMContext):
    data = await state.get_data()
    selected_services = data.get("service_ids")

    if selected_services:
        services = await Service.filter(id__in=selected_services).all()
    else:
        services = []
    expires_at = data.get("expires_at")
    if expires_at:
        expires_at = dt.now() + td(seconds=expires_at)
    discount = await Discount.create(
        percentage=data.get("percentage"),
        expires_at=expires_at,
        use_counts=data.get("use_counts"),
        code=data.get("code"),
    )
    await discount.services.add(*services)
    await query.answer(
        f"✅ تخفیف {discount.id} ساخته شد!",
        show_alert=True,
    )
    await state.clear()
    await show_discount(
        query,
        user,
        callback_data=Discounts.Callback(
            discount_id=discount.id, action=DiscountsAction.show
        ),
        state=state,
    )


# Show Discounts
@router.callback_query(
    IsSuperUser(),
    Discounts.Callback.filter(F.action == DiscountsAction.show),
)
async def show_discount(
    query: CallbackQuery,
    user: User,
    callback_data: Discounts.Callback,
    state: FSMContext | None = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    discount = (
        await Discount.filter(id=callback_data.discount_id)
        .prefetch_related("services")
        .first()
    )
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )
    services = "\n".join(
        [f"{service.id}: {service.name}" for service in discount.services]
    )
    text = f"""
آیدی تخفیف: <b>{discount.id}</b>
کد تخفیف: <code>{discount.code if discount.code else '➖'}</code>
محدودیت استفاده: <code>{discount.use_counts if discount.use_counts else '♾'}</code>

تعداد دفعات استفاده شده: <code>{discount.used_times}</code>

درصد: <code>{discount.percentage}</code>
تاریخ انقضا: <b>{helpers.hr_date(discount.expires_at.timestamp()) if discount.expires_at else '♾'}</b>

لینک استفاده مستقیم:\n {f'https://t.me/{get_bot_username()}?start=dis_{discount.code}' if discount.code else '➖'}

سرویس‌هایی که روی آن‌ها اعمال می‌شود: 
{services if services else 'همه سرویس‌ها'}
    """
    await query.message.edit_text(
        text, reply_markup=DiscountAct(discount=discount).as_markup()
    )


# Remove Discounts
@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.rem),
    IsSuperUser(),
)
async def remove_discount(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    discount = await Discount.filter(id=callback_data.discount_id).first()
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        text = """
مطمئن هستید که میخواهید تخفیف را حذف کنید؟: 
"""
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmDiscountAction(
                discount=discount, action=DiscountActAction.rem
            ).as_markup(),
        )
    await discount.delete()
    await query.answer("تخفیف حذف شد!", show_alert=True)
    return await show_discounts(
        query,
        user,
    )


@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.flip_is_active),
    IsSuperUser(),
)
async def discount_flip_active(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    discount = await Discount.filter(id=callback_data.discount_id).first()
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )

    if not callback_data.confirmed:
        if discount.is_active:
            text = """
    مطمئن هستید که میخواید تخفیف را غیرفعال کنید؟: 
    """
        else:
            text = """
    مطمئن هستید که میخواید تخفیف را فعال کنید؟: 
    """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmDiscountAction(
                discount=discount, action=DiscountActAction.flip_is_active
            ).as_markup(),
        )
    if discount.is_active:
        discount.is_active = False
        text = "تخفیف غیرفعال شد!"
    else:
        discount.is_active = True
        text = "تخفیف فعال شد!"
    await discount.save()
    await query.answer(text, show_alert=True)
    await show_discount(
        query,
        user,
        callback_data=Discounts.Callback(
            discount_id=discount.id, action=DiscountsAction.show
        ),
    )


@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.flip_on_purchase),
    IsSuperUser(),
)
async def flip_discount_on_purchase(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    discount = await Discount.filter(id=callback_data.discount_id).first()
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        if discount.on_purchase:
            text = """
مطمئن هستید که میخواهید تخفیف روی خرید سرویس جدید اعمال نشود؟
            """
        else:
            text = """
مطمئن هستید که میخواهید تخفیف روی خرید سرویس جدید اعمال شود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmDiscountAction(
                discount=discount,
                action=DiscountActAction.flip_on_purchase,
            ).as_markup(),
        )
    if discount.on_purchase:
        discount.on_purchase = False
        text = "تخفیف روی خرید غیرفعال شد!"
    else:
        discount.on_purchase = True
        text = "تخفیف روی خرید فعال شد!"
    await discount.save()
    await query.answer(text, show_alert=True)
    await show_discount(
        query,
        user,
        callback_data=Discounts.Callback(
            discount_id=discount.id, action=DiscountsAction.show
        ),
    )


@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.flip_on_renew),
    IsSuperUser(),
)
async def flip_discount_on_renew(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    discount = await Discount.filter(id=callback_data.discount_id).first()
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        if discount.on_renew:
            text = """
مطمئن هستید که میخواهید تخفیف روی تمدید سرویس اعمال نشود؟
            """
        else:
            text = """
مطمئن هستید که میخواهید تخفیف روی تمدید سرویس اعمال شود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmDiscountAction(
                discount=discount,
                action=DiscountActAction.flip_on_renew,
            ).as_markup(),
        )
    if discount.on_renew:
        discount.on_renew = False
        text = "تخفیف روی تمدید غیرفعال شد!"
    else:
        discount.on_renew = True
        text = "تخفیف روی تمدید فعال شد!"
    await discount.save()
    await query.answer(text, show_alert=True)
    await show_discount(
        query,
        user,
        callback_data=Discounts.Callback(
            discount_id=discount.id, action=DiscountsAction.show
        ),
    )


@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.flip_once_per_user),
    IsSuperUser(),
)
async def flip_discount_once_flip_once_per_user(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    discount = await Discount.filter(id=callback_data.discount_id).first()
    if not discount:
        await query.answer("تخفیف یافت نشد!", show_alert=True)
        return await show_discounts(
            query,
            user,
        )

    if not callback_data.confirmed:
        await query.answer()
        if discount.once_per_user:
            text = """
مطمئن هستید که میخواهید تخفیف به ازای هر کاربر بیشتر از یک بار استفاده شود؟
            """
        else:
            text = """
مطمئن هستید که میخواهید تخفیف به ازای هر کاربر فقط یک بار استفاده شود؟
            """
        return await query.message.edit_text(
            text,
            reply_markup=ConfirmDiscountAction(
                discount=discount,
                action=DiscountActAction.flip_once_per_user,
            ).as_markup(),
        )
    if discount.once_per_user:
        discount.once_per_user = False
        text = "به ازای هر کاربر فقط یک بار غیرفعال شد!"
    else:
        discount.once_per_user = True
        text = "به ازای هر کاربر فقط یک بار فعال شد!"
    await discount.save()
    await query.answer(text, show_alert=True)
    await show_discount(
        query,
        user,
        callback_data=Discounts.Callback(
            discount_id=discount.id, action=DiscountsAction.show
        ),
    )


@router.callback_query(
    DiscountAct.Callback.filter(F.action == DiscountActAction.edit),
    IsSuperUser(),
)
async def edit_discount(
    query: CallbackQuery, user: User, callback_data: DiscountAct.Callback
):
    return await query.answer("NotImplemented!")
