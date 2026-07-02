# Web panel (main admin + reseller)

> Stable design spec for the web panel. CLAUDE.md carries a 3-line summary + this pointer.
> **Build status & remaining work → `ROADMAP.md`** (Done log + Now/Next/Backlog); this file keeps
> only the *stable* design spec (stack, theme, menu, UX rules) so it doesn't cost tokens every session.

Current state: **BUILT and substantial.** A separate **FastAPI** backend (`app/api/`, JWT auth, role-scoped) + a **React/Vite/Refine/AntD** frontend (`webpanel/`), sharing the bot's DB/Redis and the panel adapter (`docs/panels.md`). Most of P5–P13 shipped (dashboard, users 360°, services CRUD incl. create-from-scratch with a panel-aware provisioning picker, panels CRUD, reports + Jalali, resellers, discounts, texts/buttons editors, audit, alert config, force-join editor, panel-health widget, theme/font/calendar/density). The legacy `app/views` (aiohttp) still serves payment IPN + panel webhooks.

**Hard rule:** the API process **must NOT import `app.main`** (it pulls the bot/Dispatcher). It reads/writes the key-value `BotSetting`/`BotText` tables directly and signals the bot via Redis `settings:dirty`/`texts:dirty` flags (picked up by `jobs/sync_settings.py`).

## Stack (agreed)

- **Backend: FastAPI** (separate service beside the bot, sharing the same DB/Redis and **the same adapter layer**). Fully async; Pydantic + auto OpenAPI; JWT; Tortoise initialized manually in the app `lifespan` (NOT `register_tortoise` — a custom lifespan replaces its startup hook; see `app/api/main.py`).
- **Frontend: React + TypeScript + Vite + Refine + Ant Design.** CRUD-heavy panel is fast with Refine (data/auth providers + RBAC); AntD has ready tables/forms/dashboards and **built-in RTL** for Persian. State via TanStack Query.
- **Theme target** (captured from the `Dashboard-Example-Theme-UI/` mockup so it never needs re-reading): RTL Persian, **Vazirmatn** UI font + **IBM Plex Mono** for numerals, **Material Symbols Rounded** icons, **emerald/green accent**, **dark + light** themes (CSS-var/oklch palette with green/red/amber/blue/violet status colors), layout = fixed **sidebar (~266px, grouped nav) + sticky topbar (title, search, lang + theme toggles, notifications) + card grid**. Must be **fully responsive** (sidebar → drawer on mobile). Map onto the AntD `ConfigProvider` theme tokens.
- **Auth:** JWT (access + refresh); role from `User.Role`. In Guardino multi-tenant mode, reseller web login can also validate against Guardino Hub.
- **Deploy:** new services (`api` + built frontend behind nginx or served by the api) added to `docker-compose`, same DB/Redis. Bot and web panel share one source of truth (models + adapters).
- **Bilingual: Persian + English** (Persian default). RTL for Persian (AntD `ConfigProvider` + i18n, e.g. react-i18next); all UI strings translatable, no hard-coded copy.

## Coverage requirement (agreed — scoped, do NOT explode)

The admin panel must be complete, tidy, and extensible. "Complete" means everything needed to **manage the bot and sell** is manageable from the panel: bot management, service sales, users, orders, payments, resellers, services, servers/panels, links, nodes/groups, reports, and settings — across the **Marzban, PasarGuard, and Guardino Hub** paths **through the same adapter layer**. Anything available in the Telegram bot for a user/admin/reseller should also be available in the web panel, more structured and controllable.
**The goal is NOT to re-create upstream panels like Guardino Hub from scratch** — only to fully cover the sales/management/support/reporting/day-to-day operations of the bot.

## Suggested menu structure

```text
Dashboard            → Overview · Sales Summary · System Health · Low Balance Alerts
Users & Subscriptions→ Users · Proxies/Subscriptions · Renew/Extend · Reset Usage · Links/QR · Import/Sync
Orders & Payments    → Orders · Invoices · Transactions · Payment Gateways · Failed Payments · Refunds
Plans & Sales        → Services/Plans · Service Menus · Discounts · Pricing Rules · Test Service Rules
Panels & Nodes       → Connected Panels · Marzban Servers · PasarGuard Groups · Guardino Nodes · Link Policy · Panel Health
Resellers            → Reseller List · Reseller Users · Wallet/Credit · Permissions · Pricing/Margin · Reports
Automation           → Broadcast · Scheduled Jobs · Reminders · Low Balance Notifications · Logs
Reports              → Sales · Revenue · Reseller · Usage · Payment
Settings             → Bot Settings · Texts · Force Join · Security · Environment Checks · Admin Settings
```

## UX rules

- Per user/subscription: a detail page with tabs `Overview`, `Links`, `Orders`, `Payments`, `Panel Status`, `Logs`.
- Dangerous ops (delete, refund, reset usage, revoke link) require a confirmation modal; payment/balance ops stay idempotent.
- Resellers get a simpler menu with strict data scoping (only their own `parent` subtree); they must NOT see panel credentials, global bot settings, or system-wide reports.
- Guardino-specific settings (**Link Policy**, **Low Balance Thresholds**) live under Settings/Panels, not inside user pages. PasarGuard `Groups`/`proxy_settings` live on the service/panel page.
- Dashboard is a concise summary: today's sales, successful/failed orders, active users, Guardino reseller balance, panel errors, job status.
- Keep an **audit log** of admin/reseller actions; offer a read-only **"view as reseller"** for support.

## Shared principles

- Keep web-panel code separate from Telegram handlers: `app/api/` (web/API), shared business logic in services/helpers, `app/panels/` (adapters).
- Role separation: super_user / admin / support / reseller (ordered `User.Role` ints — support is
  the receipt reviewer and, like resellers, is subtree-scoped by the API `_scope` helpers).
- Never leak secrets/panel tokens/payment creds/bot token/DB details in web responses.
- Reuse the same Tortoise models and panel layer (`docs/panels.md`); don't duplicate logic.
