import json
import re
import textwrap
from abc import ABC
from html import escape
from typing import Any, Callable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from pydantic import BaseModel, model_validator

from app.keyboards.admin.admin import CancelFormAdmin


class TextValue(BaseModel, ABC):
    class Config:
        extra = "forbid"

    value: str
    _allowed_variables: dict[str, Callable[[Any], str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _load_from_str(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"value": data}
        return data


def admin_edit_texts_format(ed_text: TextValue, field: str) -> str:
    text = f"""
برای ویرایش متن زیر از دکمه «ویرایش» استفاده کنید:
({field})
==================<blockquote>\n{escape(ed_text.value)}\n</blockquote>==================
<a href='https://core.telegram.org/bots/api#html-style'>می توانید از تگ‌های html برای فرمت متن استفاده کنید!</a>
"""
    if ed_text._allowed_variables:
        text += """
************************
متغیرهای قابل استفاده در این متن:
"""
        text += "\n".join(
            f"<code>{{{t}}}</code>" for t in ed_text._allowed_variables.keys()
        )
    return text


def admin_edit_texts_test_variables(
    ed_text: TextValue, text: str
) -> tuple[bool, list[str]]:
    """Checks if the variables passed from user are allowed

    Args:
        ed_text (TextValue): original texts field
        text (str): new text field

    Returns:
        tuple[bool, list[str]]: [True if no error found else False, variables not found in _allowed_variables]
    """
    if not ed_text._allowed_variables:
        return True, []

    not_found_vars = []
    for v in re.finditer(r"\{[a-zA-Z0-9_]*\}", text, re.MULTILINE):
        if v.group().strip("{}") not in ed_text._allowed_variables:
            not_found_vars.append(v.group())
    if not_found_vars:
        return False, not_found_vars
    return True, []


async def check_texts(ed_text: TextValue, message: Message) -> bool:
    result = admin_edit_texts_test_variables(ed_text=ed_text, text=message.text)
    if not result[0]:
        not_found_vars = [f"<code>{{{t}}}</code>" for t in result[1]]
        allowed_vars = [f"<code>{{{t}}}</code>" for t in ed_text._allowed_variables]
        text = f"""
متغیرهای زیر که تعریف کرده‌اید مجاز نیستند!

{', '.join(not_found_vars)}

متغیرهای مجاز:
{', '.join(allowed_vars)}
"""
        await message.answer(
            text=text,
            reply_markup=CancelFormAdmin().as_markup(
                resize_keyboard=True, one_time_only=True
            ),
        )
        return False

    try:
        msg = await message.answer(text=message.text)
        await msg.delete()
        return True
    except TelegramBadRequest as exc:
        await message.answer(f"Error: {exc}")
        raise exc


def format_number(value: int | float) -> str:
    return f"{value:,}" if value is not None else None


def format_config_links(value: list[str]) -> str:
    if not value:
        return ""
    return "\n\n".join([f"<code>{link}</code>" for link in value])


def format_active_inbounds(value: list[str]) -> str:
    # PasarGuard/Guardino user records carry no inbound list — never render a
    # literal "None"; the sub link activates every protocol automatically.
    if not value:
        return "<b>خودکار (از طریق لینک اشتراک)</b>"
    return ", ".join([f"<b>{t.upper()}</b>" for t in value])


def format_card_number(value: str) -> str:
    return f"{value}"
