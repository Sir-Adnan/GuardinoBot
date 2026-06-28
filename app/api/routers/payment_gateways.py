"""Payment-gateway config (super-admin).

Reads/writes the per-gateway JSON stored in the key-value ``BotSetting`` table
(``payment_*`` keys — each holds a gateway's pydantic Settings serialized to
JSON). The API must NOT import ``app.utils.settings`` (it pulls ``app.main``), so
we touch ``BotSetting`` directly and signal the bot via the ``settings:dirty``
Redis flag (picked up by ``jobs/sync_settings.py``).

SECURITY: secrets (``api_key`` / ``ipn_secret_key``) are **masked** on read and
only overwritten when a non-empty new value is sent — an empty value is a no-op,
so a save never accidentally wipes a key. Field names (never values) are audited.
"""

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

import config
from app.api.clients import bot, redis
from app.api.deps import require_role
from app.api.schemas import (
    GatewayFieldOut,
    GatewayOut,
    GatewaysOut,
    GatewayUpdateIn,
    OfflineConfigOut,
    OfflineConfigUpdateIn,
    OfflinePendingItem,
    OfflinePendingOut,
    OfflineReviewIn,
    OkOut,
    PlisioCurrenciesOut,
    PlisioCurrencyOut,
)
from app.models.setting import BotSetting
from app.models.user import CryptoPayment, Transaction, User
from app.plugins.payment.crypto.plisio import (
    DEFAULT_INVOICE_CURRENCY,
    FALLBACK_CURRENCIES,
    PlisioAPI,
    PlisioError,
    Settings as PlisioSettings,
    is_usdt_currency,
)
from app.utils.audit import record_audit

router = APIRouter(prefix="/payment-gateways", tags=["payment-gateways"])

_DIRTY = "settings:dirty"
_SECRET_FIELDS = {"api_key", "ipn_secret_key"}
_OFFLINE_KEY = "payment_offline"
_REVIEW_QUEUE = "offline:review:queue"  # the bot drains this (jobs/sync_settings)


def _slug(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")
    return out or "coin"

# Curated, manageable gateways → fields. kind: bool | int | str | secret.
_GATEWAYS: dict[str, dict] = {
    "payment_nowpayments": {
        "name": "NowPayments",
        "type": "crypto",
        "fields": {
            "enabled": "bool",
            "menu_title": "str",
            "min_pay_amount": "int",
            "api_key": "secret",
            "ipn_secret_key": "secret",
            "pay_currency": "str",
            "rate_provider": "str",
            "rate_cache_seconds": "int",
            "usdt_margin_percent": "str",
            "manual_usdt_toman_rate": "str",
        },
    },
    "payment_plisio": {
        "name": "Plisio",
        "type": "crypto",
        "fields": {
            "enabled": "bool",
            "menu_title": "str",
            "min_pay_amount": "int",
            "api_key": "secret",
            "api_base": "str",
            "default_currency": "str",
            "allowed_currencies": "list_str",
            "expire_min": "int",
            "return_existing": "int",
            "rate_provider": "str",
            "rate_cache_seconds": "int",
            "usdt_margin_percent": "str",
            "manual_usdt_toman_rate": "str",
        },
    },
}

_GATEWAY_DEFAULTS = {
    "payment_nowpayments": {
        "api_key": config.NP_API_KEY,
        "ipn_secret_key": config.NP_IPN_SECRET_KEY,
        "pay_currency": config.NP_PAY_CURRENCY,
        "rate_provider": config.PAYMENT_RATE_PROVIDER,
        "rate_cache_seconds": config.PAYMENT_RATE_CACHE_SECONDS,
        "usdt_margin_percent": config.PAYMENT_USDT_MARGIN_PERCENT,
        "manual_usdt_toman_rate": config.MANUAL_USDT_TOMAN_RATE,
    }
}


async def _read_json(key: str) -> dict:
    rows = await BotSetting.filter(_key=key).values("_value")
    raw = (rows[0]["_value"] if rows else "") or ""
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _mask(v: Optional[str]) -> str:
    s = str(v or "")
    if not s:
        return ""
    return ("•" * (len(s) - 4) + s[-4:]) if len(s) > 4 else "•" * len(s)


def _field_out(name: str, kind: str, data: dict) -> GatewayFieldOut:
    if kind == "secret":
        val = data.get(name)
        return GatewayFieldOut(name=name, kind=kind, is_set=bool(val), hint=_mask(val))
    return GatewayFieldOut(name=name, kind=kind, value=data.get(name))


async def _out() -> GatewaysOut:
    gateways = []
    for key, spec in _GATEWAYS.items():
        data = await _read_json(key)
        data = {**_GATEWAY_DEFAULTS.get(key, {}), **data}
        if key == "payment_plisio":
            data = PlisioSettings(**data).model_dump()
        gateways.append(
            GatewayOut(
                key=key,
                name=spec["name"],
                type=spec["type"],
                fields=[_field_out(n, k, data) for n, k in spec["fields"].items()],
            )
        )
    return GatewaysOut(gateways=gateways)


@router.get("", response_model=GatewaysOut)
async def list_gateways(
    _: User = Depends(require_role(User.Role.super_user)),
) -> GatewaysOut:
    return await _out()


@router.patch("", response_model=GatewaysOut)
async def update_gateway(
    body: GatewayUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> GatewaysOut:
    spec = _GATEWAYS.get(body.key)
    if not spec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown gateway")
    data = await _read_json(body.key)
    changed: list[str] = []
    for fname, kind in spec["fields"].items():
        if fname not in body.values:
            continue
        v = body.values[fname]
        if kind == "bool":
            data[fname] = bool(v)
        elif kind == "int":
            try:
                data[fname] = max(0, int(v or 0))
            except (ValueError, TypeError):
                continue
        elif kind == "list_str":
            if isinstance(v, str):
                items = v.split(",")
            elif isinstance(v, list):
                items = v
            else:
                items = []
            clean: list[str] = []
            seen: set[str] = set()
            for item in items:
                code = str(item or "").strip().upper()
                if code and code not in seen:
                    seen.add(code)
                    clean.append(code)
            data[fname] = clean
        elif kind == "secret":
            sv = str(v or "").strip()
            if not sv:  # empty = no change — never wipe a key on save
                continue
            data[fname] = sv
        else:  # str
            value = (str(v).strip() or None) if v is not None else None
            if fname == "rate_provider":
                value = (value or "nobitex").lower()
                if value not in {"nobitex", "manual"}:
                    value = "nobitex"
            if body.key == "payment_plisio" and fname == "default_currency":
                value = value.upper() if value else DEFAULT_INVOICE_CURRENCY
                if not is_usdt_currency(value):
                    value = DEFAULT_INVOICE_CURRENCY
            data[fname] = value
        changed.append(fname)

    if changed:
        # Upsert: the bot creates each payment_* row on startup, but a freshly
        # added gateway (e.g. payment_plisio before a restart) may not exist yet —
        # so create it if the update touched no row. Stored as JSON (the bot
        # validates the gateway's pydantic Settings from it, filling defaults).
        encoded = json.dumps(data, ensure_ascii=False)
        await BotSetting.update_or_create(
            defaults={"_value": encoded},
            _key=body.key,
        )
        await redis.set(_DIRTY, "1")
        await record_audit(
            action="payment_gateway.update",
            actor=actor,
            target_type="payment_gateway",
            target_id=body.key,
            detail={"changed": changed},  # field NAMES only, never secret values
        )
    return await _out()


def _plisio_currency_items(items: list[dict]) -> list[PlisioCurrencyOut]:
    out: list[PlisioCurrencyOut] = []
    for item in items:
        cid = str(item.get("cid") or item.get("psys_cid") or "").strip().upper()
        if not cid:
            continue
        try:
            hidden = int(item.get("hidden") or 0)
        except (TypeError, ValueError):
            hidden = 0
        out.append(
            PlisioCurrencyOut(
                cid=cid,
                currency=str(item.get("currency") or ""),
                name=str(item.get("name") or cid),
                icon=str(item.get("icon") or ""),
                precision=str(item.get("precision") or ""),
                hidden=hidden,
                maintenance=bool(item.get("maintenance")),
            )
        )
    return out


@router.get("/plisio/currencies", response_model=PlisioCurrenciesOut)
async def plisio_currencies(
    _: User = Depends(require_role(User.Role.super_user)),
) -> PlisioCurrenciesOut:
    data = await _read_json("payment_plisio")
    api_key = str(data.get("api_key") or "").strip()
    api_base = str(data.get("api_base") or "").strip() or None
    if api_key:
        try:
            items = await PlisioAPI.get_currencies(
                api_key=api_key, api_base=api_base, fiat="USD"
            )
            normalized = _plisio_currency_items(items)
            if normalized:
                return PlisioCurrenciesOut(items=normalized, fallback=False)
        except PlisioError:
            pass
    return PlisioCurrenciesOut(
        items=_plisio_currency_items(FALLBACK_CURRENCIES),
        fallback=True,
    )


# -- offline (manual) crypto gateway: wallet-per-coin -------------------------
async def _offline_out() -> OfflineConfigOut:
    d = await _read_json(_OFFLINE_KEY)
    coins = [c for c in (d.get("coins") or []) if isinstance(c, dict)]
    return OfflineConfigOut(
        enabled=bool(d.get("enabled")),
        menu_title=str(d.get("menu_title") or ""),
        min_pay_amount=int(d.get("min_pay_amount") or 0),
        require_screenshot=bool(d.get("require_screenshot", True)),
        coins=coins,  # pydantic coerces each into OfflineCoin
    )


@router.get("/offline", response_model=OfflineConfigOut)
async def get_offline(
    _: User = Depends(require_role(User.Role.super_user)),
) -> OfflineConfigOut:
    return await _offline_out()


@router.put("/offline", response_model=OfflineConfigOut)
async def update_offline(
    body: OfflineConfigUpdateIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OfflineConfigOut:
    """Replace the offline-gateway config (incl. the coin→wallet list)."""
    d = await _read_json(_OFFLINE_KEY)
    if body.enabled is not None:
        d["enabled"] = bool(body.enabled)
    if body.menu_title is not None:
        d["menu_title"] = body.menu_title.strip()
    if body.min_pay_amount is not None:
        d["min_pay_amount"] = max(0, int(body.min_pay_amount))
    if body.require_screenshot is not None:
        d["require_screenshot"] = bool(body.require_screenshot)
    if body.coins is not None:
        clean: list[dict] = []
        seen: set[str] = set()
        for c in body.coins:
            addr = (c.address or "").strip()
            label = (c.label or "").strip()
            if not addr or not label:
                continue  # skip incomplete rows
            code = (c.code or "").strip() or _slug(label)
            if code in seen:
                code = f"{code}_{len(clean)}"
            seen.add(code)
            clean.append(
                {
                    "code": code,
                    "label": label,
                    "network": (c.network or "").strip(),
                    "address": addr,
                    "enabled": bool(c.enabled),
                    "auto_check": bool(c.auto_check),
                }
            )
        d["coins"] = clean

    encoded = json.dumps(d, ensure_ascii=False)
    await BotSetting.update_or_create(
        defaults={"_value": encoded},
        _key=_OFFLINE_KEY,
    )
    await redis.set(_DIRTY, "1")
    await record_audit(
        action="payment_gateway.offline",
        actor=actor,
        target_type="payment_gateway",
        target_id=_OFFLINE_KEY,
        detail={"coins": len(d.get("coins", [])), "enabled": d.get("enabled")},
    )
    return await _offline_out()


# -- offline: pending payments review (read + web→bot approve/reject) ----------
@router.get("/offline/pending", response_model=OfflinePendingOut)
async def offline_pending(
    _: User = Depends(require_role(User.Role.super_user)),
) -> OfflinePendingOut:
    rows = (
        await CryptoPayment.filter(
            provider=CryptoPayment.Provider.offline,
            transaction__status=Transaction.Status.waiting,
        )
        .prefetch_related("transaction__user")
        .order_by("-id")
        .limit(100)
    )
    items = []
    for cp in rows:
        tx = cp.transaction
        u = tx.user
        ed = cp.extra_data or {}
        items.append(
            OfflinePendingItem(
                cp_id=cp.id,
                transaction_id=tx.id,
                user_id=u.id,
                username=u.username,
                amount=tx.amount,
                coin_label=str(ed.get("coin_label") or cp.pay_currency or ""),
                network=str(ed.get("network") or ""),
                txid=str(ed.get("txid") or ""),
                has_screenshot=bool(ed.get("screenshot")),
                created_at=cp.created_at,
            )
        )
    return OfflinePendingOut(items=items)


@router.get("/offline/{cp_id}/screenshot")
async def offline_screenshot(
    cp_id: int, _: User = Depends(require_role(User.Role.super_user))
):
    """Proxy the customer's payment screenshot (a Telegram file) for review."""
    cp = await CryptoPayment.filter(
        id=cp_id, provider=CryptoPayment.Provider.offline
    ).first()
    if cp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    file_id = (cp.extra_data or {}).get("screenshot")
    if not file_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No screenshot")
    try:
        f = await bot.get_file(file_id)
        buf = await bot.download_file(f.file_path)
        data = buf.read() if hasattr(buf, "read") else buf
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not fetch screenshot")
    return Response(content=data, media_type="image/jpeg")


@router.post("/offline/{cp_id}/review", response_model=OkOut)
async def offline_review_web(
    cp_id: int,
    body: OfflineReviewIn,
    actor: User = Depends(require_role(User.Role.super_user)),
) -> OkOut:
    """Queue an approve/reject for the BOT to apply (credit + notify + activate
    run in the bot process). Idempotent — the bot re-checks status."""
    action = "approve" if body.action == "approve" else "reject"
    cp = await CryptoPayment.filter(
        id=cp_id, provider=CryptoPayment.Provider.offline
    ).prefetch_related("transaction").first()
    if cp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if cp.transaction.status == Transaction.Status.finished:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already approved")
    await redis.rpush(
        _REVIEW_QUEUE, json.dumps({"cp_id": cp_id, "action": action})
    )
    await record_audit(
        action="offline_payment.review",
        actor=actor,
        target_type="offline_payment",
        target_id=str(cp_id),
        detail={"action": action},
    )
    return OkOut(ok=True)
