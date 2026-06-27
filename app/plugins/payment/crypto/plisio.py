"""Plisio crypto-gateway API client + callback verification.

Foundation module (no bot wiring yet): a small httpx client for creating Plisio
invoices and a SECURITY-CRITICAL callback verifier.

Callback auth (mirrors Plisio's reference `verifyCallbackData`):
  1. pull `verify_hash` out of the POSTed data,
  2. `ksort` the remaining fields by key,
  3. cast `expire_utc` to string + html-unescape `tx_urls` (as the PHP code does),
  4. PHP-`serialize()` the assoc array (every value is a string — Plisio signs over
     `$_POST`, so values arrive as strings),
  5. `HMAC-SHA1(serialized, api_key)` and constant-time compare to `verify_hash`.

Getting step 4 byte-exact is what makes this safe — `_php_serialize` is unit-tested
against known PHP output (see `_selftest`). Read the callback with aiohttp
`request.post()` so values are strings, matching PHP `$_POST`.
"""

import hashlib
import hmac
import html
from typing import Any, Optional

import httpx
from httpx import Timeout

import config
from app.plugins.payment.utils import BaseSettings

PLISIO_API_URL = "https://plisio.net/api/v1"  # official OpenAPI server

SETTINGS_KEY_PREFIX = "plisio"


class Settings(BaseSettings):
    """Plisio gateway config (stored under ``payment_plisio`` in bot settings).
    Configured from the web panel — no large bot-side FSM. ``allowed_coins`` is
    the comma-separated ``allowed_psys_cids`` (e.g. ``USDT_TRX,TRX,TON,BTC``);
    empty = let Plisio offer all enabled coins."""

    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "🪙 ارز دیجیتال (Plisio)"
    api_key: Optional[str] = None
    allowed_coins: Optional[str] = None

# Plisio invoice status values. Only a fully-paid invoice should credit; an
# over/under payment is "mismatch" and must be handled by the actual received
# amount (never blind-credit the invoice amount on mismatch).
STATUS_COMPLETED = "completed"
STATUS_MISMATCH = "mismatch"
PENDING_STATUSES = {"new", "pending", "pending internal", "confirming", "expired"}


class PlisioError(Exception):
    pass


def _php_serialize(data: dict[str, Any]) -> str:
    """PHP ``serialize()`` of a flat associative array whose values are strings.

    Produces ``a:N:{s:klen:"k";s:vlen:"v";...}`` with **byte** length prefixes
    (PHP ``strlen`` counts bytes). ``None`` → empty string. Callers pass already
    key-sorted data (PHP ``ksort``)."""
    out = [f"a:{len(data)}:{{"]
    for k, v in data.items():
        ks = str(k)
        vs = "" if v is None else str(v)
        kb = ks.encode("utf-8")
        vb = vs.encode("utf-8")
        out.append(f's:{len(kb)}:"{ks}";s:{len(vb)}:"{vs}";')
    out.append("}")
    return "".join(out)


def verify_callback(post: dict[str, Any], api_key: str) -> bool:
    """True iff the Plisio callback `verify_hash` is authentic for `api_key`."""
    if not api_key or not isinstance(post, dict):
        return False
    verify_hash = post.get("verify_hash")
    if not verify_hash:
        return False
    data = {k: v for k, v in post.items() if k != "verify_hash"}
    data = {k: data[k] for k in sorted(data.keys())}  # PHP ksort (string keys)
    if "expire_utc" in data:
        data["expire_utc"] = str(data["expire_utc"])
    if "tx_urls" in data and data["tx_urls"] is not None:
        data["tx_urls"] = html.unescape(str(data["tx_urls"]))
    serialized = _php_serialize(data)
    expected = hmac.new(
        api_key.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected, str(verify_hash))


class PlisioAPI:
    BASE_URL = PLISIO_API_URL

    @classmethod
    async def _get(cls, action: str, api_key: str, params: dict[str, Any]) -> dict:
        if not api_key:
            raise PlisioError("Plisio API key is not set")
        q = {"api_key": api_key}
        q.update({k: v for k, v in params.items() if v is not None})
        async with httpx.AsyncClient(
            timeout=Timeout(15.0), proxies=config.PROXY
        ) as client:
            r = await client.get(f"{cls.BASE_URL}/{action.lstrip('/')}", params=q)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            raise PlisioError(f"Plisio: non-JSON response ({r.status_code})")
        if not isinstance(body, dict) or body.get("status") != "success":
            detail = body.get("data") if isinstance(body, dict) else None
            msg = (detail or {}).get("message") if isinstance(detail, dict) else r.text
            raise PlisioError(f"Plisio error: {msg}")
        return body.get("data") or {}

    @classmethod
    async def create_invoice(
        cls,
        *,
        api_key: str,
        order_number: str,
        order_name: str,
        source_amount: float,
        callback_url: str,
        source_currency: str = "USD",
        allowed_psys_cids: Optional[str] = None,
        description: Optional[str] = None,
        expire_min: int = 60,
    ) -> dict:
        """Create a fiat-priced invoice. Returns ``{txn_id, invoice_url,
        invoice_total_sum}``. Plisio converts the fiat `source_amount` to crypto."""
        return await cls._get(
            "invoices/new",
            api_key,
            {
                "order_number": order_number,
                "order_name": order_name,
                "source_amount": source_amount,
                "source_currency": source_currency,
                "callback_url": callback_url,
                "allowed_psys_cids": allowed_psys_cids,
                "description": description,
                "expire_min": expire_min,
            },
        )

    @classmethod
    async def validate_key(cls, api_key: str) -> bool:
        """Cheap key check — the operations list requires a valid key and no
        path params, so a non-error response means the key works."""
        await cls._get("operations", api_key, {})
        return True


def _selftest() -> None:
    """Byte-exact checks of the PHP-serialize replica (run: python plisio.py)."""
    # PHP: serialize(["amount"=>"10","status"=>"completed"])
    assert (
        _php_serialize({"amount": "10", "status": "completed"})
        == 'a:2:{s:6:"amount";s:2:"10";s:6:"status";s:9:"completed";}'
    ), "single-byte assoc serialize mismatch"
    # empty array
    assert _php_serialize({}) == "a:0:{}"
    # byte length (multibyte value): "é" is 2 bytes in UTF-8
    assert _php_serialize({"k": "é"}) == 'a:1:{s:1:"k";s:2:"é";}'
    # verify_callback round-trip with a known api_key
    key = "SECRETKEY"
    sample = {"txn_id": "abc", "order_number": "42", "status": "completed", "amount": "0.001"}
    ksorted = {k: sample[k] for k in sorted(sample)}
    good = hmac.new(
        key.encode(), _php_serialize(ksorted).encode(), hashlib.sha1
    ).hexdigest()
    assert verify_callback({**sample, "verify_hash": good}, key) is True
    assert verify_callback({**sample, "verify_hash": "deadbeef"}, key) is False
    assert verify_callback(sample, key) is False  # no hash
    print("plisio _selftest OK")


if __name__ == "__main__":
    _selftest()
