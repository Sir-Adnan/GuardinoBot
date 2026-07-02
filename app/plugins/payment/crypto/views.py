import hashlib
import hmac
import json
from typing import Any

from aiohttp import web

from app.logger import get_logger
from app.models.user import CryptoPayment
from app.utils import settings

from .nowpayments_service import (
    extract_invoice_id as np_extract_invoice_id,
    extract_order_id as np_extract_order_id,
    extract_payment_id as np_extract_payment_id,
    finalize_nowpayments_payment,
    find_nowpayments_transaction,
)
from .plisio import verify_callback as plisio_verify
from .plisio_service import (
    extract_order_number,
    extract_txn_id,
    finalize_plisio_payment,
    find_plisio_transaction,
)


logger = get_logger("plugins/payment/crypto")

routes = web.RouteTableDef()


def hmac_sign(key: str, data: str) -> str:
    """
    sign data string with key and sha512 algorithm
    """
    return hmac.new(
        key.encode(),
        data.encode(),
        hashlib.sha512,
    ).hexdigest()


def sort_data(data: dict[str, Any]) -> str:
    """
    sort data from nowpayments notification for hmac_sign
    """

    def _sort_dict(data_dict: dict[str, Any]) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    k: _sort_dict(v) if isinstance(v, dict) else v
                    for k, v in data_dict.items()
                }.items()
            )
        )

    return json.dumps(_sort_dict(data), separators=(",", ":"))


def verify_signature(sig: str, key: str, data: dict) -> bool:
    """
    verify nowpayments notification data with ipn secret key and signature
    (constant-time compare to avoid timing attacks).
    """
    if not sig or not key:
        return False
    return hmac.compare_digest(sig, hmac_sign(key, sort_data(data)))


def get_menu_title(
    provider: CryptoPayment.Provider, _settings: "settings.Settings"
) -> str:
    if provider == CryptoPayment.Provider.nowpayments:
        return _settings.payment_nowpayments.menu_title
    elif provider == CryptoPayment.Provider.plisio:
        return _settings.payment_plisio.menu_title
    elif provider == CryptoPayment.Provider.eswap:
        return _settings.payment_eswap.menu_title
    elif provider == CryptoPayment.Provider.swapino:
        return _settings.payment_swapino.menu_title
    return "-"


@routes.post("/npipn")
@routes.post("/npipn/")
async def verify_payment(request: web.Request):
    _settings = settings.get_settings()

    # Read the body defensively — it must be a JSON object.
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("payload is not a JSON object")
    except Exception:  # noqa: BLE001
        logger.warning("npipn: invalid or empty body")
        return web.Response(status=400, text="bad request")

    # SECURITY: the IPN signature is MANDATORY. Without a configured secret we
    # cannot prove the callback really came from NowPayments — an attacker could
    # POST a forged "finished" notification for any order_id and self-credit. So
    # reject when no secret is set (and on any signature mismatch).
    secret = _settings.payment_nowpayments.ipn_secret_key
    if not secret:
        logger.error(
            "npipn: IPN secret key is NOT configured — rejecting callback. Set the "
            "IPN secret in the NowPayments gateway settings to credit crypto safely."
        )
        return web.Response(status=403, text="ipn secret not configured")
    sig = request.headers.get("x-nowpayments-sig", "")
    if not verify_signature(sig, secret, data):
        logger.error("npipn: signature verification failed")
        return web.Response(status=403, text="invalid signature")

    # authenticated — log only non-sensitive identifiers
    logger.info(
        f"npipn verified: order_id={data.get('order_id')} "
        f"status={data.get('payment_status')}"
    )

    transaction = await find_nowpayments_transaction(
        order_id=np_extract_order_id(data),
        invoice_id=np_extract_invoice_id(data),
        payment_id=np_extract_payment_id(data),
    )
    if not transaction:
        logger.error(
            "npipn: transaction not found "
            f"order_id={data.get('order_id')} invoice_id={data.get('invoice_id')} "
            f"payment_id={data.get('payment_id')}"
        )
        return web.Response(status=200)

    await finalize_nowpayments_payment(transaction, data, source="callback")
    return web.Response(status=200)


async def _read_plisio_payload(request: web.Request) -> dict[str, Any]:
    wants_json = request.query.get("json") == "true"
    content_type = (request.content_type or "").lower()
    if wants_json or "json" in content_type:
        try:
            data = await request.json()
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            if wants_json:
                raise
    return dict(await request.post())


@routes.get("/payments/nowpayments/success")
async def nowpayments_success(request: web.Request):
    return web.Response(
        text="وضعیت پرداخت توسط ربات بررسی می‌شود. لطفاً به تلگرام برگردید."
    )


@routes.get("/payments/nowpayments/fail")
async def nowpayments_fail(request: web.Request):
    return web.Response(
        text="پرداخت کامل نشد یا توسط درگاه ناموفق اعلام شد. لطفاً به تلگرام برگردید.",
        status=200,
    )


@routes.get("/payments/nowpayments/partial")
async def nowpayments_partial(request: web.Request):
    return web.Response(
        text="پرداخت ناقص ثبت شده و نیاز به بررسی پشتیبانی دارد. لطفاً به تلگرام برگردید.",
        status=200,
    )


@routes.get("/payments/plisio/success")
async def plisio_success(request: web.Request):
    return web.Response(text="وضعیت پرداخت توسط ربات بررسی می‌شود. لطفاً به تلگرام برگردید.")


@routes.get("/payments/plisio/fail")
async def plisio_fail(request: web.Request):
    return web.Response(text="پرداخت کامل نشد یا توسط درگاه ناموفق اعلام شد. لطفاً به تلگرام برگردید.")


@routes.post("/payments/plisio/callback")
@routes.post("/payments/plisio/callback/")
async def verify_plisio_payment_v2(request: web.Request):
    _settings = settings.get_settings()
    api_key = _settings.payment_plisio.api_key
    if not api_key:
        logger.error("plisio: API key not configured - rejecting callback")
        return web.Response(status=403, text="not configured")

    try:
        payload = await _read_plisio_payload(request)
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="bad request")
    if not payload:
        return web.Response(status=400, text="empty body")
    if not plisio_verify(payload, api_key):
        logger.error("plisio: verify_hash verification failed")
        return web.Response(status=403, text="invalid signature")

    order_number = extract_order_number(payload)
    txn_id = extract_txn_id(payload)
    transaction = await find_plisio_transaction(
        order_number=order_number, txn_id=txn_id
    )
    if not transaction:
        logger.warning(
            f"plisio: callback for unknown transaction order={order_number} txn={txn_id}"
        )
        return web.json_response({"ok": True})

    result = await finalize_plisio_payment(transaction, payload, source="callback")
    return web.json_response({"ok": True, **result})


@routes.post("/plisio")
@routes.post("/plisio/")
async def verify_plisio_payment(request: web.Request):
    """Legacy Plisio callback path (old dashboard configs point here) —
    delegates to the v2 handler: mandatory api-key + `verify_hash`, then the
    idempotent finalizer in ``plisio_service``."""
    return await verify_plisio_payment_v2(request)
