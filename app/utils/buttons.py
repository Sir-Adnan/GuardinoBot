"""Editable main-menu button labels.

Pure data + helpers, importable by BOTH the keyboards (bot) and the FastAPI web
panel (no heavy imports here, so the API stays free of ``app.main``).

The main menu is a *reply* keyboard, so its button text doubles as the routing
key (handlers match ``F.text == MainMenu.purchase``). Custom labels are therefore
remapped back to the canonical default by ``app/middlewares/button_labels.py``
before routing; here we only own the registry + lookups.
"""

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
    "proxy_renew": "♻️ تمدید سرویس",
    "proxy_links": "🔗 دریافت لینک‌های اتصال",
    "proxy_reset_password": "🔑 تغییر پسوورد",
    "proxy_disable": "🚫 غیرفعال‌سازی موقت",
    "proxy_enable": "✅ فعال‌سازی",
    "proxy_remove": "🗑 حذف از لیست",
    "proxy_set_name": "✏️ تنظیم اسم دلخواه",
    "alert_renew": "🔄 تمدید (آلارم)",
    "alert_links": "🔗 لینک اتصال (آلارم)",
}

STYLES = ("primary", "success", "danger")

# Sensible default colours, applied only when premium buttons are enabled and the
# admin hasn't overridden the style for that key.
DEFAULT_STYLES: dict[str, str] = {
    "proxy_renew": "success",
    "proxy_enable": "success",
    "proxy_disable": "danger",
    "proxy_remove": "danger",
    "alert_renew": "success",
    "alert_links": "primary",
}


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
