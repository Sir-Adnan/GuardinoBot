"""Premium/custom-emoji + coloured INLINE buttons.

Builds an aiogram ``InlineKeyboardButton`` that, when the super-admin has enabled
premium buttons in the web panel, carries the Bot API extras
``icon_custom_emoji_id`` (a custom-emoji icon shown before the text) and
``style`` (``primary``/``success``/``danger`` colour).

Safety:
- Master switch (``settings.premium_buttons_enabled``) defaults OFF, so this is a
  plain button and behaviour is unchanged until the owner opts in.
- Custom emoji require the bot owner to have Telegram Premium; ``style`` does not.
- Build-time fallback: if the installed aiogram rejects the extra fields, a plain
  button is returned so the UI never breaks. (Reply-keyboard buttons can't carry
  these — inline only.)
"""

from typing import Optional

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton

from app.utils import buttons as _b


def premium_button(
    text: str,
    *,
    key: Optional[str] = None,
    callback_data=None,
    url: Optional[str] = None,
    web_app=None,
    icon_custom_emoji_id: Optional[str] = None,
    style: Optional[str] = None,
) -> InlineKeyboardButton:
    base: dict = {"text": text}
    if callback_data is not None:
        base["callback_data"] = (
            callback_data.pack()
            if isinstance(callback_data, CallbackData)
            else callback_data
        )
    if url is not None:
        base["url"] = url
    if web_app is not None:
        base["web_app"] = web_app

    extras: dict = {}
    # Lazy import: keeps app.utils.settings (→ app.main) out of import order.
    from app.utils.settings import get_settings

    s = get_settings()
    if getattr(s, "premium_buttons_enabled", False):
        icon = icon_custom_emoji_id or _b.resolve_icon(key, getattr(s, "button_icons", {}))
        st = style or _b.resolve_style(key, getattr(s, "button_styles", {}))
        if icon:
            extras["icon_custom_emoji_id"] = icon
        if st:
            extras["style"] = st

    if extras:
        try:
            return InlineKeyboardButton(**base, **extras)
        except Exception:  # aiogram rejected the new fields → plain button
            return InlineKeyboardButton(**base)
    return InlineKeyboardButton(**base)
