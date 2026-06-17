from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.keyboards.base import ForceJoin
from app.models.user import User
from app.utils import helpers, settings, texts
from app.utils.filters import IsJoinedToChannel

from .start import main_menu_handler

router = Router(name="base")


@router.callback_query(ForceJoin.Callback.filter())
async def check_force_join(query: CallbackQuery, user: User):
    _settings = settings.get_settings()
    if await helpers.check_force_join(
        user, force_join_chats=_settings.force_join_chats
    ):
        await query.message.edit_text("✅ عضویت شما در کانال تایید شد")
        return await main_menu_handler(query, user)
    await query.answer("🚫 عضویت شما در کانال تایید نشد!", show_alert=True)


@router.message(~IsJoinedToChannel(send_alert=False))
async def force_join_ph(message: Message):
    return


@router.message()
async def command_not_found(message: Message):
    await message.reply(texts.get_texts().command_not_found.value)
