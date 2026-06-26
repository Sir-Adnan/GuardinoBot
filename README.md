# GuardinoBot

A Telegram bot for selling proxy/VPN subscriptions, with a **multi-panel backend** (Marzban · PasarGuard · Guardino Hub) and a separate **web admin/reseller panel**.

- **Repo:** <https://github.com/Sir-Adnan/GuardinoBot> · **Author:** UnknownZero · **License:** Proprietary.
- **UI language:** Persian (bot + web panel, with English available in the panel).
- **Version:** see [`app/__init__.py`](app/__init__.py).

> خلاصهٔ فارسی: رباتِ فروشِ اشتراکِ پروکسی/VPN روی تلگرام، با پشتیبانی از سه پنل (Marzban/PasarGuard/Guardino Hub)، یک پنل وبِ مدیریت/نمایندگی، سیستم نوتیفِ هوشمند، لاگ حسابرسی، و امکانِ کاستومایزِ متن‌ها/دکمه‌ها/منوها. نصب با یک دستور (پایین).

---

## Overview

GuardinoBot sells and manages proxy subscriptions through Telegram. The core runs on **Marzban** (kept as a stable legacy path) while new development targets **PasarGuard** and **Guardino Hub**. The bot connects to every panel through one neutral adapter layer, so the create/renew/manage flow is identical regardless of the underlying panel.

**Two deployment modes:**

1. **Owner self-host** — you run your own bot and connect your own panel(s).
2. **Guardino reseller (multi-tenant)** — a reseller from Guardino Hub runs a bot that logs in with their reseller credentials (`/api/v1/reseller/...`); the hub owns base pricing/wallet and the bot adds a resale margin.

---

## Features

**Telegram bot**
- Subscription sales, renew, test services, nested service categories, discounts, referrals.
- Wallet/credit, multiple payment gateways (card-to-card, NowPayments/crypto, Perfect Money, Tronseller, Rial gateways: Zarinpal/Zibal/PayPing/AqayePardakht).
- Reseller tree (sub-resellers, per-reseller pricing/margin, postpaid).
- Force-join, phone verification, multi-language, force-reload texts/settings without restart.
- **Non-blocking broadcast** worker (throttled, resumable).

**Multi-panel** (one adapter, `app/panels/`)
- Marzban (legacy), **PasarGuard** (groups), **Guardino Hub** (nodes, GB/days, hub pricing).

**User notifications (smart alerts)** — `app/jobs/proxy_alerts.py`
- Expiry-soon, low-data, unused-subscription, and ended alerts with a one-tap **renew** button.
- Self-healing per-proxy dedup; configurable thresholds & per-type toggles.

**Web admin/reseller panel** — `app/api/` (FastAPI) + `webpanel/` (React)
- Dashboard, Users, Subscriptions, Services, **Service Menus**, Discounts, Payments, Panels, Reports, Resellers, Automation, **Audit Log**, **Bot Texts**, **Bot Buttons**, Settings.
- **Audit log** of every state-changing admin/reseller action (web + bot) to prevent financial abuse.
- Bot customization: edit message texts (with premium `<tg-emoji>` support), main-menu button labels, nested sale categories, and most bot settings.
- Telegram OTP login + Telegram Web-App auto-login; JWT; role-scoped (super_user / admin / reseller).
- RTL Persian + English, dark/light, 5 accent themes, responsive (Vazirmatn font).

---

## Architecture & stack

| Area | Tech |
|---|---|
| Bot | aiogram 3.4.1 (**polling**) |
| Lang/runtime | Python 3.11 on Docker (`python:3.11-alpine`) |
| DB | MariaDB/MySQL · Tortoise ORM 0.20 · aerich migrations |
| Cache/queue/state | Redis (FSM, APScheduler jobstore, cache) |
| Scheduler | APScheduler (`AsyncIOScheduler` + RedisJobStore) |
| Bot web server | aiohttp (`app/views`) — payment IPN + panel webhooks on `WEBAPP_PORT` (3333) |
| Panel layer | `app/panels/` neutral adapter — Marzban (`marzban_client/`, auto-gen) + hand-written httpx for PasarGuard/Guardino |
| Web API | FastAPI (`app/api/`, uvicorn :8000) — shares DB/Redis + the adapter layer |
| Web frontend | Vite + React + TS + Refine + Ant Design (`webpanel/`, nginx :8080) |
| Config | `python-decouple` from `.env` |
| Crypto | `pycryptodomex` + `SECRET_KEY_STRING` (encrypted DB fields) |

Entry: `bot.py` → `app/main.py:main()`. Startup: DB → webapp → plugins → routers → middlewares → API servers → scheduler → `run_polling`.

### Multi-panel differences

| | Marzban (legacy) | PasarGuard | Guardino Hub |
|---|---|---|---|
| Auth | admin token | admin token | reseller user/pass → access token (2FA-aware) |
| User identity | `username` | `username` | **`user_id` (int)** + label |
| Network unit | inbounds | **groups** | **nodes** |
| Volume/time | bytes / epoch | bytes / epoch | **GB / days** |
| Pricing | bot computes | bot computes | **hub computes** (`quote`) |

> Golden rule: new code never imports `marzban_client`/a panel httpx client directly — always go through `app.panels` (`get_panel(server_id)` + neutral methods).

---

## Installation

### Server (recommended)

```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardinobot.sh)
```

The installer sets up Docker, asks for an optional **domain**, generates `docker-compose.yml` + `.env`, builds the image locally, and starts everything. It installs a `guardinobot` management command with a menu: **install · update · logs · backup · restart · status · set domain · edit config · uninstall**.

- App dir: `/opt/GuardinoBot` · Data: `/var/lib/guardinobot`
- Services: `bot`, `api`, `webpanel`, `redis`, `mariadb`, `phpmyadmin` (localhost-only, via SSH tunnel), and `caddy` (auto-HTTPS, when a domain is set).
- DB migrations apply automatically on start (`prestart.sh` → `aerich upgrade`).

### Manual (dev)

```bash
cp .env.example .env      # fill BOT_TOKEN, SUPER_USERS, WEBHOOK_BASE_URL, DATABASE_URL, SECRET_KEY_STRING
docker compose up -d --build
# dev/debug compose: docker compose -f docker-compose.debug.yml up
```

---

## Configuration (`.env`)

Key variables (see [`.env.example`](.env.example) for the full list — never commit real secrets):

| Var | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `SUPER_USERS` | super-admin Telegram ids (newline-separated) |
| `DATABASE_URL` | `mysql://user:pass@mariadb:3306/db` |
| `SECRET_KEY_STRING` | encryption key for sensitive DB fields |
| `WEBHOOK_BASE_URL` | public URL for payment IPN / panel webhooks |
| `DOMAIN` | domain for the panel + bot (enables in-bot web-panel button + TWA auto-login; needs HTTPS) |
| `WEB_JWT_SECRET` | JWT secret for the web panel (defaults to `SECRET_KEY_STRING`) |
| `WEB_CORS_ORIGINS` | allowed CORS origins (`*` or comma list) |
| `PROXY` | optional SOCKS/HTTP proxy for the Telegram client |
| payment vars | per-gateway credentials (NowPayments, Perfect Money, Rial gateways, …) |

New env must be registered in `config.py` **and** `.env.example` (with an empty/safe value).

---

## Web panel

A separate FastAPI service (`api`) + React SPA (`webpanel/`), sharing the bot's DB/Redis and the §6 adapter layer.

- **Access:** open the panel URL (needs `DOMAIN`/HTTPS), or the in-bot inline **«🖥 پنل وب مدیریت»** button (admin panel) which auto-logs-in via Telegram Web-App. Otherwise use Telegram OTP login.
- **Roles:** super_user (full + audit/texts/buttons/menus/settings), admin (sales/management/reports), reseller (own subtree only, no credentials/global settings).
- **Build:** `cd webpanel && npm install && npm run build` (served by nginx, proxies `/api` → api).
- **Design intent:** purchases stay **bot-only** (user-centric); the panel covers management, support, reporting, customization, and audit — not manual money-affecting sales.

---

## Database & migrations

- Every model change needs a migration: `aerich migrate` → `aerich upgrade` (applied on container start).
- Migrations are **additive/backward-compatible**. Never drop columns/tables or rewrite financial history without explicit approval.
- Recent migrations: `46` (panel_type + service panel_config), `47` (link_policy, proxy panel ids), `48` (audit_logs), `49` (Proxy.notified for alerts).

---

## Roadmap / Phases

**Done**
- ✅ Multi-panel adapter + **PasarGuard** (data-plane + admin UI + webhook).
- ✅ **Guardino Hub** (id-based, GB/days, hub pricing; adapter + admin UX + purchase/manage + low-balance alerts).
- ✅ **Web panel** — all §9 areas (Dashboard·Users·Subscriptions·Services·Menus·Discounts·Payments·Panels·Reports·Resellers·Automation·Audit·Texts·Buttons·Settings), OTP + TWA auth.
- ✅ **Audit log** — every web write-action + key bot admin financial/structural actions (charge/decharge/undo, server & service CRUD) recorded with actor/source/target/amount.
- ✅ Bot customization — texts editor (+ custom emoji in message text), main-menu button labels, nested Service Menus, settings parity.
- ✅ **Phase 1 — User notification/alert system** (expiry/low-data/unused/ended + renew button, configurable).
- 🔄 **Phase 2 — Web UX overhaul** (in progress): Vazirmatn font, 5 accent themes + picker, tabbed Settings. Remaining: detail-page tabs (user/proxy), skeletons/empty-states, more polish.

**Planned**
- ⏳ **Phase 3 — Premium/custom emoji + colour on inline (glass) buttons** via Bot API `icon_custom_emoji_id` + `style` (`primary`/`success`/`danger`). Inline buttons only; requires the bot owner to have Telegram Premium; aiogram 3.4.1 needs a raw-payload passthrough with a safe fallback. Config per-button in the web Buttons page.
- ⏳ Bot settings-menu toggle/thresholds for alerts (web panel already covers config).
- ⏳ Force-join channel editor + payment-gateway config in the web panel.
- ⏳ Web-initiated text broadcast (cross-process worker trigger).
- ⏳ Guardino reserves + efficient paginated sync + on_hold mapping.
- ⏳ Brand migration of remaining `marzbot`/`Marzdemo` strings → Guardino.
- ⏳ aiogram upgrade (3.4.1 is old; `parse_mode=` on the constructor is deprecated).
- ⏳ Better observability (structured metrics/logs for panel & gateway errors).
- ⏳ PasarGuard native `reset_proxy_credentials` (currently a no-op).

---

## Todo

- [x] PasarGuard adapter + admin UI
- [x] Guardino Hub adapter + admin UX + purchase/manage
- [x] Web admin/reseller panel (all areas) + OTP/TWA auth
- [x] Audit log (web + bot actions)
- [x] Texts / Buttons / Service-Menus management
- [x] User notification/alert system (Phase 1)
- [x] Web UX: font + accent themes + tabbed Settings (Phase 2, partial)
- [ ] Premium emoji + colour on inline buttons (Phase 3)
- [ ] Detail-page tabs (user/proxy), skeletons, more polish
- [ ] Bot settings-menu alert toggle
- [ ] Force-join editor + payment-gateway config (web)
- [ ] Web-initiated broadcast trigger
- [ ] Guardino reserves + efficient sync + on_hold
- [ ] Brand string migration · aiogram upgrade · observability

---

## Development

```bash
# targeted checks (preferred)
python -m py_compile path/to/file.py

# heavy (gated): build/run, migrations, client regen
docker compose up -d --build
aerich migrate && aerich upgrade
make generate-client            # regenerate the Marzban client
make tag && make push           # release (CI builds the image on a v*.*.* tag)
```

See [`CLAUDE.md`](CLAUDE.md) for full contributor guidance (token economy, safety rules, the panel adapter contract, and the web-panel design).

---

## Security

- Never log or expose: bot token, payment/panel tokens, `DATABASE_URL`, `SECRET_KEY_STRING`, gateway/panel credentials, Redis/MariaDB creds.
- Sensitive values are stored encrypted (`PasswordField`). The web panel never returns panel/DB credentials.
- Payment callbacks are idempotent; financial history is never rewritten; migrations are additive.
- phpMyAdmin is bound to localhost only (reach it via an SSH tunnel).

## License

Proprietary. All rights reserved.
