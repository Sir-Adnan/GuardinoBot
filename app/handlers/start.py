from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import __version__
from app.handlers.user import account
from app.keyboards.base import MainMenu
from app.keyboards.user.purchase import Services, ServicesActions
from app.models.service import Discount, Service
from app.models.user import User
from app.utils import settings, texts
from app.utils.filters import HasAccess

router = Router(name="start")


@router.message(Command("version"))
async def version_info(message: Message, user: User):
    text = f"""
Guardino-Bot <code>v{__version__}</code> Developed by <a href='https://github.com/Sir-Adnan/GuardinoBot'>UnknownZero</a>
"""
    await message.reply(text=text)


@router.message(
    CommandStart(deep_link=True, ignore_case=True, magic=F.args.startswith("prnt_"))
)
async def parent_referred_start(
    message: Message, user: User, command: CommandObject, state: FSMContext
):
    try:
        parent_id = command.args.lstrip("prnt_")
        if (user.id == int(parent_id)) or (user.parent_id == int(parent_id)):
            raise ValueError()
        if user.parent_id:
            text = f"""
🚫 کاربر ({f'@{user.username}' if user.username else user.name}) <code>{user.id}</code> قصد ورود با لینک شما را دارد ولی از قبل به ربات دعوت شده است!
لطفا با پشتیبانی تماس بگیرید.
"""
            await message.bot.send_message(
                chat_id=parent_id,
                text=text,
            )
            raise ValueError()
    except ValueError:
        return await start_handler(message, user, command, state)

    parent = await User.filter(id=parent_id).first()
    if not parent:
        return await start_handler(message, user, command, state)

    user.parent = parent
    await user.save()
    text = f"""
✅ کاربر ({f'@{user.username}' if user.username else user.name}) <code>{user.id}</code> از طریق لینک شما وارد ربات شد!

شما می‌توانید از بخش {MainMenu.account!r} -> 'مدیریت کاربران' کاربر را مدیریت کنید!
"""
    await message.bot.send_message(
        chat_id=parent.id,
        text=text,
    )
    return await start_handler(message, user, command, state)


@router.message(~HasAccess())
async def has_access_ph(qmsg: Message | CallbackQuery):
    return


@router.message(
    CommandStart(deep_link=True, ignore_case=True, magic=F.args.startswith("dis_"))
)
async def user_discounted_start(
    message: Message, user: User, command: CommandObject, state: FSMContext
):
    discount_code = command.args.split("dis_")[1]
    discount = await Discount.filter(code=discount_code.strip()).first()
    if not discount:
        return await start_handler(message, user, command, state)

    await start_handler(message, user, command, state, start_only=True)

    await account.redeem_code(discount, message, user, state)


@router.message(
    CommandStart(deep_link=True, ignore_case=True, magic=F.args.startswith("ref_"))
)
async def user_referred_start(
    message: Message, user: User, command: CommandObject, state: FSMContext
):
    _settings = settings.get_settings()
    if _settings.referral_system:
        try:
            referrer_id = command.args.lstrip("ref_")
            if (user.id == int(referrer_id)) or user.referrer_id:
                raise ValueError()
        except ValueError:
            return await start_handler(message, user, command, state)

        referrer = await User.filter(id=referrer_id).first()
        if not referrer:
            return await start_handler(message, user, command, state)

        user.referrer = referrer
        await user.save()
        text = f"🎉 😉تبریک! یک نفر از طریق لینک شما وارد ربات شد. با اولین خرید کاربر، {_settings.referral_discount_percent} درصد از مبلغ خرید به عنوان هدیه به حساب شما اضافه می‌شود"
        await message.bot.send_message(
            chat_id=referrer.id,
            text=text,
        )
    return await start_handler(message, user, command, state)


@router.message(CommandStart(deep_link=False, ignore_case=True))
async def start_handler(
    message: Message,
    user: User,
    command: CommandObject,
    state: FSMContext,
    start_only: bool = False,
):
    await message.answer(texts.get_texts().start.value)
    if not start_only:
        await main_menu_handler(message, user, state)
        # first-touch onboarding: nudge users who have no subscription yet
        # straight to the buy flow (the reply menu has it too, but an explicit
        # inline CTA converts better). Cheap single count, no new copy/migration.
        if await user.proxies.all().count() == 0:
            await message.answer(
                "🚀 <b>به جمع ما خوش اومدی!</b>\n\n"
                "برای شروع، یک پلن انتخاب کن و در چند ثانیه اشتراکت رو فعال کن. "
                "اگر سوالی داشتی، پشتیبانی همیشه کنارته 💬",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🛒 خرید اشتراک",
                                callback_data=Services.Callback(
                                    action=ServicesActions.show
                                ).pack(),
                            )
                        ]
                    ]
                ),
            )


@router.message(F.text == MainMenu.main_menu)
@router.message(F.text.casefold() == MainMenu.cancel)
@router.message(Command(commands="menu"))
async def main_menu_handler(
    qmsg: Message | CallbackQuery,
    user: User,
    state: FSMContext = None,
):
    if (state is not None) and (await state.get_state() is not None):
        await state.clear()
    _settings = settings.get_settings()
    referral = _settings.referral_system
    if _settings.show_test_service_in_menu:
        q = Service.filter(
            server__is_enabled=True, purchaseable=True, is_test_service=True
        )
        if user.role == User.Role.user:
            q = q.filter(resellers_only=False)
        elif user.role == User.Role.reseller:
            q = q.filter(users_only=False)

        test_services = await q.all()
    else:
        test_services = []
    text = texts.get_texts().main_menu.value
    markup = MainMenu(
        test_services=test_services,
        referral=referral,
        is_super_user=user.role == User.Role.super_user,
    ).as_markup(resize_keyboard=True)
    if isinstance(qmsg, CallbackQuery):
        return await qmsg.message.answer(text=text, reply_markup=markup)
    return await qmsg.answer(text=text, reply_markup=markup)


# @router.message(
#     (F.text == MainMenu.cancel) | (F.text == MainMenu.back),
#     StateFilter(payment.CardToCardReceiptForm),
# )
# @router.message(Command(commands=["cancel"]))
# async def cancel_handler(message: Message, user: User, state: FSMContext):
#     """
#     Allow user to cancel any action
#     """
#     await main_menu_handler(message, user, state)
