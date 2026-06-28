"""Crypto payment rate helpers.

Amounts inside GuardinoBot stay in toman. Crypto gateways can use this module
to convert a toman invoice to a USDT amount without floats.
"""

from decimal import Decimal, InvalidOperation, ROUND_UP
from typing import Any

import httpx
from httpx import Timeout

import config

RATE_CACHE_KEY = "rate:usdt:toman"


class PaymentRateError(Exception):
    pass


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise PaymentRateError("invalid decimal value")
    if result <= 0:
        raise PaymentRateError("decimal value must be positive")
    return result


def _manual_rate(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return _decimal(value)
    except PaymentRateError:
        return None


def parse_nobitex_usdt_toman(data: dict[str, Any]) -> Decimal:
    stats = data.get("stats") if isinstance(data, dict) else None
    if not isinstance(stats, dict):
        raise PaymentRateError("nobitex response has no stats")
    pair = stats.get("usdt-rls")
    if not isinstance(pair, dict):
        raise PaymentRateError("nobitex response has no usdt-rls pair")
    value = pair.get("bestSell") or pair.get("latest")
    rial = _decimal(value)
    return (rial / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_UP)


async def _fetch_nobitex_usdt_toman() -> Decimal:
    try:
        async with httpx.AsyncClient(timeout=Timeout(10.0), proxies=config.PROXY) as client:
            response = await client.get(
                "https://apiv2.nobitex.ir/market/stats",
                params={"srcCurrency": "usdt", "dstCurrency": "rls"},
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PaymentRateError("nobitex request failed") from exc
    try:
        data = response.json()
    except Exception:  # noqa: BLE001
        raise PaymentRateError("nobitex returned non-json response")
    return parse_nobitex_usdt_toman(data)


async def _cache_get() -> Decimal | None:
    try:
        from app.main import redis

        raw = await redis.get(RATE_CACHE_KEY)
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    try:
        return _decimal(raw)
    except PaymentRateError:
        return None


async def _cache_set(rate: Decimal, ttl: int) -> None:
    if ttl <= 0:
        return
    try:
        from app.main import redis

        await redis.set(RATE_CACHE_KEY, str(rate), ex=ttl)
    except Exception:  # noqa: BLE001
        return


async def get_usdt_toman_rate(settings_obj: Any) -> Decimal:
    ttl = max(0, int(getattr(settings_obj, "rate_cache_seconds", 0) or 0))
    cached = await _cache_get()
    if cached is not None:
        return cached

    provider = str(getattr(settings_obj, "rate_provider", "nobitex") or "").lower()
    if provider == "nobitex":
        try:
            rate = await _fetch_nobitex_usdt_toman()
            await _cache_set(rate, ttl)
            return rate
        except PaymentRateError:
            pass

    manual = _manual_rate(getattr(settings_obj, "manual_usdt_toman_rate", None))
    if manual is not None:
        await _cache_set(manual, ttl)
        return manual
    raise PaymentRateError("could not fetch USDT/Toman rate")


def calculate_payable_usdt(
    amount_toman: int | Decimal,
    usdt_toman_rate: Decimal,
    margin_percent: Any,
) -> Decimal:
    amount = _decimal(amount_toman)
    rate = _decimal(usdt_toman_rate)
    try:
        margin = Decimal(str(margin_percent or "0"))
    except InvalidOperation:
        margin = Decimal("0")
    payable = amount / rate
    payable = payable * (Decimal("1") + margin / Decimal("100"))
    return payable.quantize(Decimal("0.0001"), rounding=ROUND_UP)
