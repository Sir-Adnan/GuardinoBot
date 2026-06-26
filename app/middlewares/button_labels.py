"""Remap a tapped main-menu button whose label was customised (in the web
panel) back to its canonical default text, so every existing
``F.text == MainMenu.X`` filter keeps matching.

No-op whenever no labels are overridden, so existing installs are unaffected
until an admin opts in. Runs as an outer message middleware (before filtering).
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.utils import buttons


class ButtonLabelMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        try:
            text = event.text
            if text:
                from app.utils.settings import get_settings

                canonical = buttons.main_menu_routing_map(get_settings()).get(text)
                if canonical and canonical != text:
                    new_event = event.model_copy(update={"text": canonical})
                    if event.bot is not None:
                        new_event = new_event.as_(event.bot)
                    event = new_event
        except Exception:  # never let label remapping break message handling
            pass
        return await handler(event, data)
