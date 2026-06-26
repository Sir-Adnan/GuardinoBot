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
from aiogram.types import InlineKeyboardButton, KeyboardButton

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
    strip_emoji: bool = True,
) -> InlineKeyboardButton:
    base: dict = {}
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

    # 1) Text rename (NOT premium-gated): a custom label from the web panel wins.
    label = _b.resolve_label(key, getattr(s, "button_texts", {}))
    if label:
        text = label

    # 2) Premium icon + colour (gated by the master switch).
    if getattr(s, "premium_buttons_enabled", False):
        icon = icon_custom_emoji_id or _b.resolve_icon(key, getattr(s, "button_icons", {}))
        st = style or _b.resolve_style(key, getattr(s, "button_styles", {}))
        if icon:
            extras["icon_custom_emoji_id"] = icon
            # The icon sits before the text → drop a duplicate leading emoji
            # (skipped when the caller routes by text and must keep it intact).
            if strip_emoji:
                text = _b.strip_leading_emoji(text)
        if st:
            extras["style"] = st

    base["text"] = text

    if extras:
        try:
            return InlineKeyboardButton(**base, **extras)
        except Exception:  # aiogram rejected the new fields → plain button
            return InlineKeyboardButton(**base)
    return InlineKeyboardButton(**base)


def premium_reply_button(
    text: str,
    *,
    key: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None,
    style: Optional[str] = None,
    strip_emoji: bool = True,
) -> KeyboardButton:
    """A main-menu (reply) ``KeyboardButton`` that, when premium buttons are on,
    carries ``icon_custom_emoji_id`` + ``style``.

    NOTE: unlike inline buttons, ``KeyboardButton`` support for these fields is not
    in the schema this code was written against — so we add them defensively with a
    build-time fallback: if the installed aiogram rejects them, a plain button is
    returned (the menu never breaks). When an icon is applied the leading emoji is
    stripped from the text; routing stays correct via
    ``buttons.main_menu_routing_map`` (used by the button-label middleware), which
    maps the stripped/renamed text back to the canonical handler text.
    """
    from app.utils.settings import get_settings

    s = get_settings()
    extras: dict = {}
    if getattr(s, "premium_reply_enabled", False):
        icon = icon_custom_emoji_id or _b.resolve_icon(key, getattr(s, "button_icons", {}))
        st = style or _b.resolve_style(key, getattr(s, "button_styles", {}))
        if icon:
            extras["icon_custom_emoji_id"] = icon
            if strip_emoji:
                text = _b.strip_leading_emoji(text)
        if st:
            extras["style"] = st

    if extras:
        try:
            return KeyboardButton(text=text, **extras)
        except Exception:  # aiogram rejected the new fields → plain button
            return KeyboardButton(text=text)
    return KeyboardButton(text=text)
