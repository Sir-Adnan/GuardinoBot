"""Plisio crypto-gateway API client + callback verification."""

import hashlib
import hmac
import html
from decimal import Decimal
from typing import Any, Optional

import httpx
from httpx import Timeout
from pydantic import Field, field_validator, model_validator

import config
from app.plugins.payment.utils import BaseSettings

PLISIO_API_URL = config.PLISIO_API_BASE
SETTINGS_KEY_PREFIX = "plisio"

DEFAULT_ALLOWED_CURRENCIES = ["USDT_BSC", "USDT_TRX", "USDT_TON", "TRX", "TON", "LTC"]

FALLBACK_CURRENCIES = [
    {
        "cid": "USDT_BSC",
        "currency": "USDT",
        "name": "Tether USD (BEP20)",
        "icon": "",
        "precision": "6",
        "hidden": 0,
        "maintenance": False,
    },
    {
        "cid": "USDT_TRX",
        "currency": "USDT",
        "name": "Tether USD (TRC20)",
        "icon": "",
        "precision": "6",
        "hidden": 0,
        "maintenance": False,
    },
    {
        "cid": "USDT_TON",
        "currency": "USDT",
        "name": "Tether USD (TON)",
        "icon": "",
        "precision": "6",
        "hidden": 0,
        "maintenance": False,
    },
    {
        "cid": "TRX",
        "currency": "TRX",
        "name": "TRON",
        "icon": "",
        "precision": "6",
        "hidden": 0,
        "maintenance": False,
    },
    {
        "cid": "TON",
        "currency": "TON",
        "name": "Toncoin",
        "icon": "",
        "precision": "6",
        "hidden": 0,
        "maintenance": False,
    },
    {
        "cid": "LTC",
        "currency": "LTC",
        "name": "Litecoin",
        "icon": "",
        "precision": "8",
        "hidden": 0,
        "maintenance": False,
    },
]

STATUS_COMPLETED = "completed"
STATUS_MISMATCH = "mismatch"
PENDING_STATUSES = {"new", "pending", "pending internal", "confirming"}
FAILED_STATUSES = {"expired", "cancelled", "canceled", "error", "mismatch"}


class PlisioError(Exception):
    pass


def _split_codes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        code = str(item or "").strip().upper()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


class Settings(BaseSettings):
    """Plisio gateway config stored under ``payment_plisio`` in BotSetting."""

    _name = SETTINGS_KEY_PREFIX
    enabled: bool = config.PLISIO_ENABLED
    menu_title: str = "🪙 ارز دیجیتال (Plisio)"
    api_key: Optional[str] = config.PLISIO_API_KEY
    api_base: str = config.PLISIO_API_BASE
    default_currency: str = config.PLISIO_DEFAULT_CURRENCY
    allowed_currencies: list[str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_CURRENCIES.copy()
    )
    # Legacy web setting. Kept so old rows continue to validate.
    allowed_coins: Optional[str] = None
    expire_min: int = config.PLISIO_EXPIRE_MIN
    return_existing: int = config.PLISIO_RETURN_EXISTING
    rate_provider: str = config.PAYMENT_RATE_PROVIDER
    rate_cache_seconds: int = config.PAYMENT_RATE_CACHE_SECONDS
    usdt_margin_percent: str = str(config.PAYMENT_USDT_MARGIN_PERCENT)
    manual_usdt_toman_rate: Optional[str] = config.MANUAL_USDT_TOMAN_RATE

    @model_validator(mode="before")
    @classmethod
    def _legacy_allowed_coins(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("allowed_coins") and not data.get(
            "allowed_currencies"
        ):
            data = dict(data)
            data["allowed_currencies"] = data.get("allowed_coins")
        return data

    @field_validator("default_currency", mode="before")
    @classmethod
    def _normalize_default_currency(cls, value: Any) -> str:
        code = str(value or config.PLISIO_DEFAULT_CURRENCY).strip().upper()
        return code or "USDT_BSC"

    @field_validator("allowed_currencies", mode="before")
    @classmethod
    def _normalize_allowed_currencies(cls, value: Any) -> list[str]:
        return _split_codes(value) or DEFAULT_ALLOWED_CURRENCIES.copy()

    @field_validator("api_base", mode="before")
    @classmethod
    def _normalize_api_base(cls, value: Any) -> str:
        return str(value or config.PLISIO_API_BASE).strip().rstrip("/")

    def currency_codes(self) -> list[str]:
        codes = _split_codes(self.allowed_currencies) or _split_codes(self.allowed_coins)
        if not codes:
            codes = [self.default_currency]
        default = (self.default_currency or "USDT_BSC").strip().upper()
        if default and default not in codes:
            codes.insert(0, default)
        return codes


def _php_serialize(data: dict[str, Any]) -> str:
    """PHP ``serialize()`` of a flat associative array whose values are strings."""
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
    """True iff the Plisio callback ``verify_hash`` is authentic for ``api_key``."""
    if not api_key or not isinstance(post, dict):
        return False
    verify_hash = post.get("verify_hash")
    if not verify_hash:
        return False
    data = {k: v for k, v in post.items() if k != "verify_hash"}
    data = {k: data[k] for k in sorted(data.keys())}
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
    async def _request(
        cls,
        action: str,
        api_key: str,
        params: dict[str, Any] | None = None,
        *,
        api_base: str | None = None,
    ) -> dict:
        if not api_key:
            raise PlisioError("Plisio API key is not set")
        q = {"api_key": api_key}
        q.update({k: v for k, v in (params or {}).items() if v is not None})
        base_url = (api_base or cls.BASE_URL).rstrip("/")
        async with httpx.AsyncClient(
            timeout=Timeout(15.0), proxies=config.PROXY
        ) as client:
            response = await client.get(f"{base_url}/{action.lstrip('/')}", params=q)
        try:
            body = response.json()
        except Exception:  # noqa: BLE001
            raise PlisioError(f"Plisio: non-JSON response ({response.status_code})")
        if not isinstance(body, dict) or body.get("status") != "success":
            detail = body.get("data") if isinstance(body, dict) else None
            msg = (detail or {}).get("message") if isinstance(detail, dict) else response.text
            raise PlisioError(f"Plisio error: {msg}")
        return body

    @classmethod
    async def _get(
        cls,
        action: str,
        api_key: str,
        params: dict[str, Any],
        *,
        api_base: str | None = None,
    ) -> dict:
        body = await cls._request(action, api_key, params, api_base=api_base)
        return body.get("data") or {}

    @classmethod
    async def create_invoice(
        cls,
        *,
        api_key: str,
        order_number: str,
        order_name: str,
        amount: Decimal | str,
        currency: str,
        callback_url: str,
        allowed_psys_cids: Optional[str] = None,
        description: Optional[str] = None,
        expire_min: int = 30,
        return_existing: int = 0,
        success_callback_url: Optional[str] = None,
        fail_callback_url: Optional[str] = None,
        success_invoice_url: Optional[str] = None,
        fail_invoice_url: Optional[str] = None,
        api_base: str | None = None,
    ) -> dict:
        body = await cls._request(
            "invoices/new",
            api_key,
            {
                "currency": currency,
                "amount": str(amount),
                "order_number": order_number,
                "order_name": order_name,
                "callback_url": callback_url,
                "allowed_psys_cids": allowed_psys_cids,
                "description": description,
                "expire_min": expire_min,
                "return_existing": return_existing,
                "success_callback_url": success_callback_url,
                "fail_callback_url": fail_callback_url,
                "success_invoice_url": success_invoice_url,
                "fail_invoice_url": fail_invoice_url,
            },
            api_base=api_base,
        )
        data = body.get("data") or {}
        if not data.get("txn_id"):
            raise PlisioError("Plisio returned no txn_id")
        if not data.get("invoice_url"):
            raise PlisioError("Plisio returned no invoice_url")
        data["_raw"] = body
        return data

    @classmethod
    async def get_operation(
        cls,
        txn_id: str,
        *,
        api_key: str,
        api_base: str | None = None,
    ) -> dict:
        body = await cls._request(f"operations/{txn_id}", api_key, {}, api_base=api_base)
        data = body.get("data") or {}
        data["_raw"] = body
        return data

    @classmethod
    async def get_currencies(
        cls,
        *,
        api_key: str,
        fiat: str = "USD",
        api_base: str | None = None,
    ) -> list[dict[str, Any]]:
        body = await cls._request(f"currencies/{fiat}", api_key, {}, api_base=api_base)
        data = body.get("data") or []
        if not isinstance(data, list):
            raise PlisioError("Plisio returned invalid currencies data")
        return [item for item in data if isinstance(item, dict)]

    @classmethod
    async def validate_key(cls, api_key: str, api_base: str | None = None) -> bool:
        await cls._get("operations", api_key, {}, api_base=api_base)
        return True


def _selftest() -> None:
    assert (
        _php_serialize({"amount": "10", "status": "completed"})
        == 'a:2:{s:6:"amount";s:2:"10";s:6:"status";s:9:"completed";}'
    ), "single-byte assoc serialize mismatch"
    assert _php_serialize({}) == "a:0:{}"
    assert _php_serialize({"k": "é"}) == 'a:1:{s:1:"k";s:2:"é";}'

    key = "SECRETKEY"
    sample = {
        "txn_id": "abc",
        "order_number": "42",
        "status": "completed",
        "amount": "0.001",
    }
    ksorted = {k: sample[k] for k in sorted(sample)}
    good = hmac.new(
        key.encode(), _php_serialize(ksorted).encode(), hashlib.sha1
    ).hexdigest()
    assert verify_callback({**sample, "verify_hash": good}, key) is True
    assert verify_callback({**sample, "verify_hash": "deadbeef"}, key) is False
    assert verify_callback(sample, key) is False
    print("plisio _selftest OK")


if __name__ == "__main__":
    _selftest()
