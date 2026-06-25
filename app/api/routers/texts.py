"""Bot message texts — a curated, safe subset (no payment-gateway texts).
Super-admin only.

Reads/writes the ``BotText`` key-value table DIRECTLY: the API must not import
``app.utils.texts`` (it pulls ``app.main`` via the payment plugins). After a
write, a Redis flag tells the bot to reload — see ``app/jobs/sync_settings.py``.

Texts are HTML (the bot sends with parse_mode=HTML), so a super-admin may embed
Telegram **custom/premium emoji** as ``<tg-emoji emoji-id="...">💎</tg-emoji>``;
they render only if the bot's creator account has Telegram Premium. Inline-button
labels can't carry custom emoji (Telegram limitation), so this is the place for
them. Keep any ``{PLACEHOLDER}`` tokens intact.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.clients import redis
from app.api.deps import require_role
from app.api.schemas import TextItem, TextsOut, TextUpdateIn
from app.models.setting import BotText
from app.models.user import User
from app.utils.audit import record_audit

router = APIRouter(prefix="/texts", tags=["texts"])

# Curated editable texts + the {VARIABLES} each supports (mirrors
# app/utils/texts.py). Payment-gateway texts are intentionally excluded.
_TEXTS: dict[str, list[str]] = {
    "start": [],
    "main_menu": [],
    "force_join": [],
    "purchase": [],
    "support": [],
    "help": [],
    "command_not_found": [],
    "proxy_help": ["SUBSCRIPTION_URL", "ACTIVE_INBOUNDS", "CONFIG_LINKS"],
    "referral_banner_text": ["INVITE_LINK"],
    "charge": [],
    "verify_phone_number": [],
}
_DIRTY = "texts:dirty"


@router.get("", response_model=TextsOut)
async def get_texts(
    _: User = Depends(require_role(User.Role.super_user)),
) -> TextsOut:
    rows = await BotText.filter(_key__in=list(_TEXTS)).values("_key", "_value")
    raw = {r["_key"]: r["_value"] for r in rows}
    return TextsOut(
        items=[
            TextItem(key=k, value=raw.get(k) or "", variables=v)
            for k, v in _TEXTS.items()
        ]
    )


@router.patch("", response_model=TextItem)
async def update_text(
    body: TextUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> TextItem:
    if body.key not in _TEXTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown text key")
    # Empty → reset: the bot's Texts.from_db refills an empty row with the
    # built-in default on next reload.
    await BotText.update(**{body.key: body.value})
    await redis.set(_DIRTY, "1")
    await record_audit(
        action="text.update",
        actor=actor,
        target_type="text",
        target_id=body.key,
        target_label=body.key,
    )
    rows = await BotText.filter(_key=body.key).values("_value")
    cur = rows[0]["_value"] if rows else body.value
    return TextItem(key=body.key, value=cur or "", variables=_TEXTS[body.key])
