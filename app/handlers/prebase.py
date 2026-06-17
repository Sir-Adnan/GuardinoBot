"""Handlers in this file runs before all user validation such as PhoneNumberVerify and CheckForceJoin..."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards.base import MainMenu
from app.models.user import User
from app.utils import texts

router = Router(name="prebase")


@router.message(F.text == MainMenu.support)
async def support(message: Message, user: User):
    await message.answer(texts.get_texts().support.value, disable_web_page_preview=True)


@router.message(Command("help"))
@router.message(F.text == MainMenu.help)
async def shelp(message: Message, user: User):
    await message.answer(texts.get_texts().help.value, disable_web_page_preview=True)
