"""Bot button customisation. Super-admin only.

Two parts, both stored as JSON fields on the bot's Settings model (in
``bot_settings``) so a write + the existing ``settings:dirty`` flag makes the bot
pick them up without a restart:

- **Main-menu labels** (``button_labels``) — reply-keyboard button text. The bot
  remaps a tapped custom label back to its canonical default for routing
  (app/middlewares/button_labels).
- **Inline-button premium emoji + colour** (``premium_buttons_enabled``,
  ``button_icons``, ``button_styles``) — Bot API ``icon_custom_emoji_id`` +
  ``style`` on inline (glass) buttons. Master switch defaults OFF. Custom emoji
  require the bot owner to have Telegram Premium; ``style`` does not. Reply-menu
  buttons can't carry these (inline only).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import (
    ButtonItem,
    ButtonsOut,
    ButtonsUpdateIn,
    InlineButtonItem,
)
from app.models.setting import BotSetting
from app.models.user import User
from app.utils.audit import record_audit
from app.utils.buttons import (
    DEFAULT_STYLES,
    INLINE_BUTTONS,
    MAIN_LAYOUT_KEYS,
    MAIN_MENU_BUTTONS,
    STYLES,
    resolve_main_layout,
)

router = APIRouter(prefix="/buttons", tags=["buttons"])

_LABELS = "button_labels"
_ICONS = "button_icons"
_BTN_STYLES = "button_styles"
_TEXTS = "button_texts"
_LAYOUT = "main_menu_layout"
_ENABLED = "premium_buttons_enabled"
_DIRTY = "settings:dirty"


async def _read_json(key: str) -> dict:
    rows = await BotSetting.filter(_key=key).values("_value")
    if not rows or not rows[0]["_value"]:
        return {}
    try:
        v = json.loads(rows[0]["_value"])
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


async def _read_list(key: str) -> list:
    rows = await BotSetting.filter(_key=key).values("_value")
    if not rows or not rows[0]["_value"]:
        return []
    try:
        v = json.loads(rows[0]["_value"])
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


async def _read_bool(key: str) -> bool:
    rows = await BotSetting.filter(_key=key).values("_value")
    return bool(rows) and rows[0]["_value"] not in ("", "0", "false", "False", None)


async def _out() -> ButtonsOut:
    labels = await _read_json(_LABELS)
    icons = await _read_json(_ICONS)
    styles = await _read_json(_BTN_STYLES)
    texts = await _read_json(_TEXTS)
    return ButtonsOut(
        items=[
            ButtonItem(key=k, default=d, value=str(labels.get(k) or ""))
            for k, d in MAIN_MENU_BUTTONS.items()
        ],
        premium_enabled=await _read_bool(_ENABLED),
        inline=[
            InlineButtonItem(
                key=k,
                label=label,
                text=str(texts.get(k) or ""),
                icon=str(icons.get(k) or ""),
                style=str(styles.get(k) or ""),
                default_style=DEFAULT_STYLES.get(k, ""),
            )
            for k, label in INLINE_BUTTONS.items()
        ],
        main_layout=resolve_main_layout(await _read_list(_LAYOUT)),
    )


@router.get("", response_model=ButtonsOut)
async def get_buttons(
    _: User = Depends(require_role(User.Role.super_user)),
) -> ButtonsOut:
    return await _out()


@router.patch("", response_model=ButtonsOut)
async def update_buttons(
    body: ButtonsUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> ButtonsOut:
    changes: dict = {}

    if body.labels is not None:
        clean: dict[str, str] = {}
        for key, label in body.labels.items():
            if key not in MAIN_MENU_BUTTONS:
                continue
            label = (label or "").strip()
            if label and label != MAIN_MENU_BUTTONS[key]:
                clean[key] = label
        # Reject collisions: a custom label must not equal another button's
        # default or another custom label (the routing remap would be ambiguous).
        defaults_of_others = {
            v for k, v in MAIN_MENU_BUTTONS.items() if k not in clean
        }
        seen: set[str] = set()
        for key, label in clean.items():
            if label in defaults_of_others or label in seen:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Label '{label}' collides with another button",
                )
            seen.add(label)
        changes[_LABELS] = clean

    if body.premium_enabled is not None:
        changes[_ENABLED] = bool(body.premium_enabled)

    if body.icons is not None:
        changes[_ICONS] = {
            k: str(v).strip()
            for k, v in body.icons.items()
            if k in INLINE_BUTTONS and str(v).strip()
        }

    if body.styles is not None:
        changes[_BTN_STYLES] = {
            k: v
            for k, v in body.styles.items()
            if k in INLINE_BUTTONS and v in STYLES
        }

    if body.texts is not None:
        changes[_TEXTS] = {
            k: str(v).strip()
            for k, v in body.texts.items()
            if k in INLINE_BUTTONS and str(v).strip()
        }

    if body.main_layout is not None:
        # Keep only known keys; drop empty rows. Stored [] resets to the default.
        cleaned = [
            [k for k in row if k in MAIN_LAYOUT_KEYS]
            for row in body.main_layout
            if isinstance(row, list)
        ]
        changes[_LAYOUT] = [row for row in cleaned if row]

    if changes:
        await BotSetting.update(**changes)
        await redis.set(_DIRTY, "1")
        await record_audit(
            action="buttons.update",
            actor=actor,
            target_type="buttons",
            detail={"changed": list(changes)},
        )
    return await _out()
