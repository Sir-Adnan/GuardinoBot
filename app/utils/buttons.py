"""Editable main-menu button labels.

Pure data + helpers, importable by BOTH the keyboards (bot) and the FastAPI web
panel (no heavy imports here, so the API stays free of ``app.main``).

The main menu is a *reply* keyboard, so its button text doubles as the routing
key (handlers match ``F.text == MainMenu.purchase``). Custom labels are therefore
remapped back to the canonical default by ``app/middlewares/button_labels.py``
before routing; here we only own the registry + lookups.
"""

import re

# key -> default label. Must stay in sync with app/keyboards/base.py MainMenu.
MAIN_MENU_BUTTONS: dict[str, str] = {
    "purchase": "🚀 خرید اشتراک",
    "proxies": "📍 اشتراک‌های من",
    "account": "💎 حساب من",
    "charge": "💰 شارژ حساب",
    "referral": "👥 زیرمجموعه گیری",
    "help": "🗒 راهنما",
    "support": "☑️ پشتیبانی",
    "admin_menu": "⚙️ پنل مدیریت",
}


def resolve(key: str, overrides: dict | None) -> str:
    """Custom label for ``key`` if set & non-empty, else the built-in default."""
    default = MAIN_MENU_BUTTONS[key]
    if not overrides:
        return default
    custom = (overrides.get(key) or "").strip()
    return custom or default


def reverse_map(overrides: dict | None) -> dict[str, str]:
    """custom-label -> canonical default-label, for the routing remap middleware.
    Only entries whose custom value differs from the default are included."""
    out: dict[str, str] = {}
    if not overrides:
        return out
    for key, default in MAIN_MENU_BUTTONS.items():
        custom = (overrides.get(key) or "").strip()
        if custom and custom != default:
            out[custom] = default
    return out


# --- INLINE (glass) buttons: premium-emoji icon + colour --------------------
# Unlike the main menu (a reply keyboard, label-only), inline buttons support a
# custom-emoji icon and a colour via the Bot API InlineKeyboardButton fields
# `icon_custom_emoji_id` and `style`. These are the buttons the super-admin can
# decorate from the web panel (key -> human label, for the editor UI).
INLINE_BUTTONS: dict[str, str] = {
    # -- subscription panel (proxy.ProxyPanel) --
    "proxy_renew": "♻️ تمدید سرویس",
    "proxy_links": "🔗 دریافت لینک‌های اتصال",
    "proxy_reset_password": "🔑 تغییر پسوورد",
    "proxy_disable": "🚫 غیرفعال‌سازی موقت",
    "proxy_enable": "✅ فعال‌سازی",
    "proxy_remove": "🗑 حذف از لیست",
    "proxy_set_name": "✏️ تنظیم اسم دلخواه",
    "proxy_delete_payback": "🗑 حذف و بازگشت وجه",
    # -- proxy alert messages (jobs.proxy_alerts) --
    "alert_renew": "🔄 تمدید (آلارم)",
    "alert_links": "🔗 لینک اتصال (آلارم)",
    # -- account menu (account.UserPanel — the 💎 حساب من screen) --
    "account_charge": "💳 شارژ حساب",
    "account_referral": "💎 زیرمجموعه گیری",
    "account_proxies": "📍 اشتراک‌های من",
    "account_redeem": "🎁 ثبت کد تخفیف",
    "account_settings": "⚙️ تنظیمات حساب",
    "account_manage_users": "👥 مدیریت کاربران",
    # -- purchase flow (purchase.PurchaseService) --
    "purchase_buy": "🛒 خرید سرویس",
    "purchase_pay": "💳 پرداخت (CTA)",
    "purchase_redeem": "🎁 کد تخفیف دارم",
    # -- charge flow (payment.SelectPayAmount) --
    "pay_custom_amount": "✍️ مبلغ دلخواه",
    # -- renew flow (proxy.RenewSelectMethod / ConfirmRenew) --
    "renew_now": "♻️ تمدید آنی اشتراک",
    "renew_reserve": "🌀 پلن پشتیبان (تمدید خودکار)",
    "renew_confirm": "✅ فعالسازی",
}

STYLES = ("primary", "success", "danger")

# Sensible default colours, applied only when premium buttons are enabled and the
# admin hasn't overridden the style for that key.
DEFAULT_STYLES: dict[str, str] = {
    "proxy_renew": "success",
    "proxy_enable": "success",
    "proxy_disable": "danger",
    "proxy_remove": "danger",
    "proxy_delete_payback": "danger",
    "alert_renew": "success",
    "alert_links": "primary",
    "account_charge": "primary",
    "purchase_buy": "success",
    "purchase_pay": "success",
    "renew_now": "success",
    "renew_confirm": "success",
}


# A leading run of emoji / pictographs / dingbats (+ variation selectors, ZWJ,
# regional-indicator flags, keycaps) followed by optional spaces. Persian/Arabic
# letters (U+0600–06FF) are outside these ranges, so labels are never harmed.
_LEADING_EMOJI = re.compile(
    r"^(?:[\U0001F000-\U0001FAFF☀-➿←-⇿⬀-⯿"
    r"️‍⃣〰〽\U0001F1E6-\U0001F1FF]+)\s*"
)


def strip_leading_emoji(text: str) -> str:
    """Drop a leading emoji (and the space after it). Used when a premium
    ``icon_custom_emoji_id`` is applied, so the icon doesn't double up with an
    emoji already baked into the button text."""
    if not text:
        return text
    return _LEADING_EMOJI.sub("", text, count=1).strip() or text


def resolve_label(key: str | None, texts: dict | None) -> str | None:
    """Custom (renamed) text for an inline button ``key``, or None for default.
    Renaming is NOT premium-gated — any admin can relabel a button."""
    if not key or not texts:
        return None
    return (texts.get(key) or "").strip() or None


def resolve_icon(key: str | None, icons: dict | None) -> str | None:
    """Configured custom_emoji_id for ``key``, or None."""
    if not key or not icons:
        return None
    return (icons.get(key) or "").strip() or None


def resolve_style(key: str | None, styles: dict | None) -> str | None:
    """Configured colour for ``key`` (override → default), or None if invalid."""
    val = ((styles or {}).get(key) or "").strip() if key else ""
    val = val or DEFAULT_STYLES.get(key or "", "")
    return val if val in STYLES else None
