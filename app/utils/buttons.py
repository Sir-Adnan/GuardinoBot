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
