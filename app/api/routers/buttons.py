"""Bot button labels — customise the main-menu (reply keyboard) button text.
Super-admin only.

Stored as a single ``button_labels`` JSON row in ``bot_settings`` (a field on the
bot's Settings model), so writing it + the existing ``settings:dirty`` flag makes
the bot pick up new labels without a restart. The bot remaps a tapped custom
label back to its canonical default for routing (app/middlewares/button_labels).

Show/hide toggles for optional buttons live under Settings (e.g.
``reset_password_button``, ``show_connect_links_button``,
``show_test_service_in_menu``). Note: inline-button labels can't carry custom
emoji and aren't covered here — this is the reply main menu only.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import ButtonItem, ButtonsOut, ButtonsUpdateIn
from app.models.setting import BotSetting
from app.models.user import User
from app.utils.audit import record_audit
from app.utils.buttons import MAIN_MENU_BUTTONS

router = APIRouter(prefix="/buttons", tags=["buttons"])

_KEY = "button_labels"
_DIRTY = "settings:dirty"


async def _read_overrides() -> dict:
    rows = await BotSetting.filter(_key=_KEY).values("_value")
    if not rows or not rows[0]["_value"]:
        return {}
    try:
        v = json.loads(rows[0]["_value"])
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


@router.get("", response_model=ButtonsOut)
async def get_buttons(
    _: User = Depends(require_role(User.Role.super_user)),
) -> ButtonsOut:
    overrides = await _read_overrides()
    return ButtonsOut(
        items=[
            ButtonItem(key=k, default=default, value=str(overrides.get(k) or ""))
            for k, default in MAIN_MENU_BUTTONS.items()
        ]
    )


@router.patch("", response_model=ButtonsOut)
async def update_buttons(
    body: ButtonsUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> ButtonsOut:
    # Keep only known keys with a non-empty, trimmed custom label.
    clean: dict[str, str] = {}
    for key, label in body.labels.items():
        if key not in MAIN_MENU_BUTTONS:
            continue
        label = (label or "").strip()
        if label and label != MAIN_MENU_BUTTONS[key]:
            clean[key] = label

    # Reject collisions: a custom label must not equal another button's default
    # or another custom label, or the remap/routing would be ambiguous.
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

    await BotSetting.update(**{_KEY: clean})
    await redis.set(_DIRTY, "1")
    await record_audit(
        action="buttons.update",
        actor=actor,
        target_type="buttons",
        detail={"labels": clean},
    )
    return ButtonsOut(
        items=[
            ButtonItem(key=k, default=default, value=str(clean.get(k) or ""))
            for k, default in MAIN_MENU_BUTTONS.items()
        ]
    )
