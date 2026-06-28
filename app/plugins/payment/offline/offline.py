"""Offline (manual) crypto gateway — settings only.

Admin sets a wallet address per coin (USDT-BEP20, TRX, TON, …). The customer
picks a coin, pays to that address, then submits the TXID + a screenshot; an
admin (or an optional on-chain auto-check) confirms and credits. The bot-side
flow + admin review live in a separate handler module (loaded via the plugin
handlers list); this lightweight module is imported by ``app.utils.settings``
and must NOT pull heavy/bot imports (keeps the settings import clean).
"""

from typing import Optional

from pydantic import BaseModel

from app.plugins.payment.utils import BaseSettings

SETTINGS_KEY_PREFIX = "offline"


class CoinWallet(BaseModel):
    code: str  # stable id, e.g. "usdt_trc20"
    label: str  # shown to the customer, e.g. "USDT (TRON · TRC20)"
    network: str  # e.g. "TRC20" / "BEP20" / "TON" — used for the (future) on-chain check
    address: str  # the wallet address the customer pays to
    enabled: bool = True
    # optional on-chain auto-check (per coin); off by default → manual review.
    auto_check: bool = False


class Settings(BaseSettings):
    """Stored under ``payment_offline`` in bot settings (JSON). ``coins`` is the
    list of accepted coin→wallet entries."""

    _name = SETTINGS_KEY_PREFIX
    menu_title: str = "🪙 پرداختِ دستیِ ارز دیجیتال"
    require_screenshot: bool = True  # also ask for a payment screenshot, not just TXID
    coins: list[CoinWallet] = []

    def enabled_coins(self) -> list[CoinWallet]:
        return [c for c in (self.coins or []) if c.enabled and c.address.strip()]

    def coin_by_code(self, code: str) -> Optional[CoinWallet]:
        for c in self.coins or []:
            if c.code == code:
                return c
        return None
