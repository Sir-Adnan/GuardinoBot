# CLAUDE.md — GuardinoBot

> Guide for Claude Code in this repo. Read before changing anything.
> Keep changes safe, targeted, modular, and token-efficient.
> (Written in English on purpose — fewer tokens per session than Persian.
> Bot UI strings stay Persian; this file is internal guidance only.)
>
> **Docs split:** this file = stable "how to work here" (auto-loaded every session, keep lean).
> `ROADMAP.md` = the changing plan (phases, status, todo) — read on demand. `README.md` = public docs.

---

## 0) Token economy (most important — always)

Goal: max quality, min tokens. The repo is large; blind/whole-file reads are banned.

**Read/Search**
- Never read a whole dir or big file "to be safe". Grep/Glob to the exact spot, then Read with `offset`/`limit`.
- Do NOT read these unless strictly required (100KB+, repetitive): `marzban_client/`, `Dashboard-Example-Theme-UI/` (87KB html + 57KB `support.js` — a visual-only mockup; its theme is already captured in §9, so don't re-read it), and `docs/references/upstream-apis/*.json` — the vendor specs `Marzban-API.json` / `Pasarguard-API.json` / `Guardino-API.json` / `NOWPayments-API.json` / `Plisio-API.json` (100–760KB; **parse with a `python -c json` script to the one endpoint you need; never Read whole**). To understand panel behavior, read the neutral interface in `app/panels/base.py`, not the raw spec.
- Don't read all of `migrations/models/`; only the latest or the one you need.
- For codebase-wide search where you only need a conclusion (not raw content), use the `Explore` subagent so raw output stays out of the main context.

**Edit**
- Small change → `Edit`, not full `Write`. Read a file once before editing; don't re-read it "to confirm" after a successful edit.
- Batch independent edits to one file in one message (applied in order); use `replace_all` for a repeated identical pattern.
- Match surrounding style; never rewrite unrelated sections.

**Replies**
- Short and direct; don't re-summarize what's already settled.
- When the decision is clear, act — give one recommendation, not a long option list.
- Don't echo tool output; state the result only.
- Plan + confirm before expensive work (big refactor, client regen, whole-file rewrite).

**Parallelism:** send independent tool calls together in one message.

**Bot runtime cost:** batch panel API calls (`get_users` with a username list); no per-item loops; use Redis cache; don't refetch large remote user lists.

---

## 1) Never auto-run heavy commands

After a normal edit, **never** auto-run:

```bash
docker compose up --build
docker compose up -d --build
docker compose build
docker compose logs -f
docker compose down
docker compose down -v
pip install -r requirements.txt
pip install <package>
aerich migrate
aerich upgrade
aerich init-db
python -m compileall .
make generate-client
openapi-python-client update
```

Run a heavy command only when the user types exactly one of: `FULL TEST`, `FULL BUILD`, `DEPLOY CHECK`.

**Destructive** commands — never run without an explicit request (they wipe DB/Redis/volumes): `docker compose down -v`, `docker volume rm`, `docker system prune`.

Before any long command, briefly say why and get confirmation.

**Targeted checks (default):**
- Small Python change → that file only: `python -m py_compile path/to/file.py`
- A few related files → just those.
- Whole-repo compile only on explicit request.
- If a local dependency is missing, don't auto-install; report and ask.

---

## 2) Project goal & status

**GuardinoBot** is a Telegram subscription-sales bot (proxy/VPN) — **proprietary** source owned by this project.
Repo: <https://github.com/Sir-Adnan/GuardinoBot> — developer/owner: **UnknownZero**.

**Naming:** official name is **GuardinoBot**. A few legacy brand strings (`marzbot`/`Marzdemo`) still linger in corners of the code; migrate them gradually (default username prefix, brand strings). Don't change DB table/column names without a migration + approval.

**Status:** the core runs on the **Marzban** panel. **Marzban is kept as a stable legacy path** (no new development); new development targets **PasarGuard** and **Guardino Hub**.

**Goals (in priority order):**
1. Add **PasarGuard** and **Guardino Hub** as primary sales panels (Marzban stays legacy). The bot must connect **exactly like Marzban** (same create/renew/manage flow).
2. **Advanced web panel** for the main admin and resellers, separate from the Telegram UI (§9).
3. Bug fixes / improvements (§17) — top priority: non-blocking broadcast.

**Two deployment modes the bot must support:**
- **Owner self-host:** the owner runs their own bot and connects their own panel(s) (Marzban/PasarGuard/Guardino).
- **Guardino reseller (multi-tenant):** a reseller from **Guardino Hub** runs a bot instance that logs in with **their own Guardino reseller username/password** and uses `/api/v1/reseller/...`. Here the **hub** owns base pricing/wallet; the bot adds a resale margin for the end customer.

UI language is **Persian**; keep user-facing strings Persian unless asked otherwise.

Verify current code before assuming a path, model name, DB table, migration state, or runtime behavior.

---

## 3) Architecture & stack

| Area | Tech |
|---|---|
| Bot | aiogram 3.4.1 (**polling**, not webhook) |
| Lang/runtime | Python 3.11 on Docker (`python:3.11-alpine`) |
| DB | MariaDB/MySQL via **Tortoise ORM 0.20** + **aerich** migrations |
| Cache/queue/state | **Redis** — FSM storage, APScheduler jobstore, cache |
| Scheduler | APScheduler (`AsyncIOScheduler` + RedisJobStore) |
| Web server | aiohttp (`app/views`) for payment IPN + panel webhooks on `WEBAPP_PORT` (default 3333) |
| Web panel | **FastAPI** (`app/api/`, JWT, separate process — must NOT import `app.main`) + **React/Vite/Refine/AntD** (`webpanel/`); shares DB/Redis + §6 adapter (§9) |
| Panel layer | **`app/panels/`** neutral adapter (§6). Marzban on `marzban_client/` (auto-gen); PasarGuard + Guardino are hand-written httpx. Specs: `docs/references/upstream-apis/Pasarguard-API.json` / `Guardino-API.json` (heavy — don't read unless needed) |
| Config | `python-decouple` from `.env` (sample: `.env.example`) |
| Crypto | `pycryptodomex` + `SECRET_KEY_STRING` (`PasswordField`) |

Entry: `bot.py` → `app/main.py:main()`.
Startup order: DB → webapp → plugins → routers → middlewares → API servers → scheduler → `run_polling`.

> Always confirm these details against the code (versions may have changed).

---

## 4) Directory map

```text
app/
  main.py            # bootstrap: bot, dp, redis, scheduler
  marzban.py         # legacy registry (Marzban.servers) + setup_api; also refreshes PanelRegistry on startup
  panels/            # ★ neutral adapter layer (§6): base, marzban, pasarguard, guardino, registry
  api/               # ★ FastAPI WEB-PANEL backend (§9): routers/ (dashboard, users, services,
                     # servers, proxies, transactions, reports, resellers, discounts, menus,
                     # buttons, texts, settings, audit, automation), deps/auth (JWT), schemas, clients
  handlers/
    admin/           # admin, user, server, service, service_menu, setting, payment, discount
    user/            # account, payment, proxy, purchase, ...
    start.py, base.py, prebase.py, errors.py
  keyboards/         # mirrors handlers (admin/* and user/*) + premium.py (inline emoji/colour)
  models/            # Tortoise: user, server, service, proxy, setting
  plugins/
    payment/         # crypto/{nowpayments(+_service),plisio(+_payment,_service),rates,swapino,clients,views},
                     # offline/, card_to_card, perfect_money, rial_gateway (zarinpal/zibal/payping/aqaye_pardakht), tronseller
    referral/
  jobs/              # check_reserves, del_unpaid_payments, refresh_proxies, remind_invoices,
                     # proxy_alerts, check_hub_balance, sync_settings
  middlewares/       # acl, rate_limit
  utils/             # helpers, settings, texts, encryption, proxy_management, qr, broadcast, ...
  views/             # aiohttp: status, notifications (panel webhook)
  templates/         # jinja2 (currently only payment.html)
webpanel/            # ★ React+TS+Vite+Refine+AntD web panel frontend (§9) — src/{pages,components,...}
marzban_client/      # ❗ auto-generated — do not hand-edit (§7)
migrations/models/   # aerich migrations
docs/references/upstream-apis/  # vendor API specs (NOWPayments/Plisio/Marzban/PasarGuard/Guardino) — heavy, parse don't read whole
scripts/             # import/migrate + backup
config.py            # reads env + TORTOISE_ORM
```

Don't assume the map is complete; search the repo before changing.

---

## 5) Data models (key)

- **User** — roles in `User.Role`: `user(0)`, `reseller(1)`, `admin(2)`, `super_user(3)`. Reseller tree (parent/child), referrer, balance/postpaid, `UserSetting`.
- **Server** — panel connection: `host`, `port`, `https`, `token`, `username/password` (encrypted), `is_enabled`, `total_proxies`, **`panel_type`** (enum `marzban`/`pasarguard`/`guardino`, default `marzban`), and **`link_policy`** (enum `master_first`/`node_first` — Guardino only, which sub link to show).
- **Service / ServiceMenu** — plans: `data_limit`, `expire_duration`, `inbounds` (Marzban: protocol→tags), `flow`, `price`, discount, nested menus, filters; and **`panel_config`** (JSON nullable — PasarGuard: `{"group_ids":[...], "proxy_settings":{...}}`; Guardino: `{"total_gb", "days"|"duration_preset", "node_ids"|"node_group", "pricing_mode"}`).
- **Proxy** — a user's subscription on a Server; unique `username`, `status` (ProxyStatus == PanelUserStatus values), `service`, `user`, `server`, `reserve`; for id-based panels (Guardino): **`panel_user_id`** (int, hub user id) + **`sub_token`** (master_sub_token).
- **Invoice / Transaction (+payment subtypes) / Discount / Reserve / PurchaseLog**.

User balance is **computed** (`User.get_balance` = sum of transactions minus invoices), not a stored raw value.

> Panel migrations exist and are additive: `46_*` (`Server.panel_type` + `Service.panel_config`) and `47_*` (`Server.link_policy`, widen `Server.username`→64, `Proxy.panel_user_id` + `Proxy.sub_token`). Applied automatically on container start (`prestart.sh` → `aerich upgrade`); the installer/update path does the same.

---

## 6) Multi-panel adapter (Marzban + PasarGuard + Guardino)

Don't extend the bot as Marzban-only. New panel support goes through one adapter layer:

```text
Telegram Bot / Web Panel → Business Services → Panel Adapter Interface
        → Marzban Adapter / PasarGuard Adapter / Guardino Adapter
```

**Golden rule:** new code **never** imports `marzban_client` or a panel httpx client directly; always go through `app.panels` (`get_panel(server_id)` + neutral methods).

**`BasePanel`** (`app/panels/base.py`): `get_admin`, `get_inbounds`, `create_user`, `modify_user(ModifyUserParams)`, `get_user`, `get_users` (batch), `remove_user`, `reset_usage`, `revoke_subscription`, `set_status`, `reset_proxy_credentials`, and `service_modify_params(service, existing)` which hides the provisioning difference (Marzban: inbounds/proxies preserving UUID; PasarGuard: group_ids; Guardino: none). DTOs: `PanelUser`, `ModifyUserParams` (sentinel `UNSET`), `PanelUserStatus`, `AdminInfo`. Errors are unified as `PanelError`/`PanelAuthError` (with `status_code`). `PanelRegistry` builds/caches an adapter per `Server.panel_type`.

**PasarGuard (phase 1 — done):** full lightweight-httpx adapter. Data-plane fully migrated: `handlers/user/purchase.py` (create), `handlers/user/proxy.py` (view/enable-disable/delete/revoke/reset/links/renew), `jobs/check_reserves.py`, `jobs/refresh_proxies.py`, `utils/proxy_management.py` (bulk), `models/service.get_inbounds`. Admin UI: add-server `panel_type` step + service builder with **group selection** (`SelectGroups` → `Service.panel_config.group_ids`). Webhook in `views/notifications.py` is panel-agnostic.
Remaining (minor): `reset_proxy_credentials` unsupported on PasarGuard (raises) — "change password" button is a no-op, but "smart reconnect" (revoke_sub) works; `add_user_from_subscription` (sub-token lookup) intentionally left on the Marzban legacy path.

### Fundamental differences (per the specs — read before adapter work)

| | Marzban (legacy) | PasarGuard v5 | Guardino Hub v0.1 |
|---|---|---|---|
| Auth | `/api/admin/token` (OAuth2 password → Bearer) | `/api/admin/token` (same as Marzban) | `/api/v1/auth/login` (JSON user/pass, **2FA**, api-token) |
| Bot connection | base_url + admin token | base_url + admin token | base_url + **reseller user/pass** → access_token |
| User identity | `username` | `username` | **`user_id` (int)** + `label` |
| Create user | `POST /api/user` (inbounds + proxies) | `POST /api/user` (**group_ids** + **proxy_settings**) | `POST /api/v1/reseller/user-ops` (label, **total_gb**, **days**, node_ids, pricing_mode) |
| Volume/time | bytes / seconds (epoch) | bytes / seconds | **GB / days** |
| Pricing | bot computes | bot computes | **hub computes** (`quote`, `charged_amount`, `balance_after`) |
| Network unit | inbounds | **groups** (`group_ids`) | **nodes** (`node_ids`) |
| Subscription | `/sub/{token}` | `/sub/{token}` | `master_sub_token` → `/api/v1/sub/{token}` + per-node links |
| Key ops | modify/reset/revoke/remove | + `set_status`, `active_next` | extend/renew/add-traffic/decrease-time/change-nodes/refund/set-status/reset-usage/revoke |

**Guardino status (phase 2 — core done):**
- ✅ Stage 0 (model + migration 47): `Server.link_policy`, `Proxy.panel_user_id`+`sub_token`, widen `Server.username`.
- ✅ Stage 1 (adapter `app/panels/guardino.py`): login (2FA-aware) with token cache + 401 re-auth; GB↔bytes, days↔seconds mapping; BasePanel methods (`get_admin`, `get_inbounds`=catalog, `create_user`, `modify_user`=status only, `get_user/get_users` by id, `remove_user`=refund-delete, `reset_usage`, `revoke`); Guardino-only methods: **`quote`, `get_balance`, `renew_user`, `extend`, `add_traffic`, `change_nodes`, `get_links(policy)`**. Id-based: pass `str(user_id)` in the username slot; `create_user` returns it as `PanelUser.remote_id` and stashes `master_sub_token`/`charged_amount`/`balance_after` in `raw`. Module helpers `login()/validate()` for the connect flow.
- ✅ Stage 2 (admin UX): `handlers/admin/server.py` add-server flow has a **Guardino** option → reseller user/pass login (`guardino.login`+`validate`) + **link_policy** step (master_first/node_first), stored on the new `Server` row; `ping_servers` is now panel-agnostic via `get_panel().get_admin()`. `handlers/admin/service.py` + `keyboards/admin/service.py` add a **`SelectNodes`** picker (parallel to `SelectGroups`) → `Service.panel_config = {node_ids, pricing_mode}`; node selection is optional (empty → hub default node mode); volume/time reuse the standard `data_limit`/`expire_duration` fields (adapter derives total_gb/days).
- ✅ Stage 3 (purchase + manage): `purchase.py` Guardino create stores `panel_user_id`/`sub_token` and pre-checks hub balance via `quote`/`get_balance`. The adapter resolves a passed label→user_id (cached) and `get_user` enriches `subscription_url`/`links` from `get_links`, so the existing display/QR/enable/disable/delete/revoke/reset-usage paths work for Guardino **unchanged**; `proxy.py` renew has a Guardino branch (`renew_user`). Also fixed §17 bug 2 (reseller test counting) + `count >= limit`.
- ✅ Stage 4 (low-balance alerts): `jobs/check_hub_balance.py` — every 30 min reads each Guardino server's reseller balance (`get_balance`) and warns super-users (`config.SUPER_USERS`) on two thresholds (`guardino_balance_warn`=1,000,000 / `guardino_balance_critical`=500,000 in settings), with Redis anti-spam (alert only on worsening severity).
- **Known gaps (deferred):** Guardino **reserves** (pre-bought backup plan, `check_reserves`/`renew_proxy_reserve`) still use the modify(expire/data_limit) path → not supported for Guardino; the generic `refresh_proxies` sync works for Guardino but is per-user (resolve+fetch) — a dedicated paginated reseller-sync would be more efficient. Guardino **on_hold** create isn't mapped (services with `create_on_hold_users` shouldn't target Guardino yet).
- ⚠️ **2FA must be OFF for the bot account** (unattended re-login can't solve a TOTP challenge) or the adapter raises a clear error. `modify_user` only supports `status`; volume/time changes go through `renew_user/add_traffic/extend`.

**Guardino — locked decisions (agreed with owner):**
- **Credentials:** set up with **reseller or super-admin** hub user/pass (owner has no api-token). Store password **encrypted** (`PasswordField`); never reveal in messages/logs. Login via `/api/v1/auth/login`; token/session + 2FA handled inside the adapter (api-token optional later). Don't connect to the hub's internal DB.
- **Link policy (admin-configurable):** prefer "node link (underlying panel: PasarGuard/WireGuard)" or "Guardino master" — admin setting on Server/Service. Source: `GET /api/v1/reseller/users/{id}/links` (`master_link` + `node_links[]`). If master is off → auto node_links. QR is built from the chosen link.
- **Low-balance alert:** a periodic job reads reseller balance (`/api/v1/auth/me` or `/reseller/stats`) and warns super-users: **< 1,000,000 toman warn, < 500,000 stronger warn** (thresholds configurable in settings). Avoid double-alerts with a Redis flag.
- **Pricing:** the **hub** sets base cost (`charged_amount`/`balance_after`); the bot keeps its retail price (`Service.price`, toman) separate and adds margin. **Each reseller's tariff differs and per-day cost is often zero/disabled** — never assume days cost anything; always rely on `quote`/`charged_amount`. Pre-check balance with `quote` before create to avoid a failed/loss-making purchase.

**PasarGuard:** manage token/session inside the adapter (refresh/expiry); don't re-fetch a reusable token; read large user lists with pagination/cache.

Before a big panel refactor, present a migration plan and get approval.

---

## 7) Auto-generated clients

- `marzban_client/` is generated by `openapi-python-client` from the Marzban spec, now at
  `docs/references/upstream-apis/Marzban-API.json` (moved from the old root `openapi.json`). **Don't hand-edit.**
- Regenerate (only with approval — touches many files): `make generate-client`. ⚠️ The `Makefile`
  still points `--path ./openapi.json` — update it to the new path before regenerating, or the spec moved.
- PasarGuard and Guardino deliberately use a small hand-written httpx client (`app/panels/pasarguard.py`, `app/panels/guardino.py`) behind `BasePanel` — no codegen needed.

---

## 8) DB & migrations (aerich)

- Every model change **needs a migration**: `aerich migrate` (create) → `aerich upgrade` (apply, in `prestart.sh` on start).
- Don't auto-run aerich (§1); explain first, then ask.
- Keep migrations backward-compatible and additive. **Without explicit user approval, never:** drop column/table, delete rows, reset reseller balance/data, rewrite proxy/user ownership, or rewrite financial history.
- Be careful with models: users, resellers/roles, proxies, servers/panels, services, invoices, transactions, payments, settings, texts.
- For M2M or model changes, mind the `_m2m_order` pattern + `describe` override in `models/__init__.py` (aerich bug workaround).
- If a migration is needed for deploy, say so explicitly. Don't auto-apply on production unless asked.
- Panel migrations `46_*` and `47_*` are additive and applied via `aerich upgrade`.

---

## 9) Web panel (main admin + reseller)

Current state: **BUILT and substantial.** The panel is a separate **FastAPI** backend (`app/api/`,
JWT auth, role-scoped) + a **React/Vite/Refine/AntD** frontend (`webpanel/`), sharing the bot's DB/
Redis and the §6 adapter. Most of P5–P13 shipped (dashboard, users 360°, services CRUD incl.
create-from-scratch with a panel-aware provisioning picker, panels CRUD, reports + Jalali, resellers,
discounts, texts/buttons editors, audit, alert config, force-join editor, panel-health widget, theme/
font/calendar/density). The legacy `app/views` (aiohttp) still serves payment IPN + panel webhooks.
The API process **must NOT import `app.main`** (it pulls the bot/Dispatcher); it reads/writes the
key-value `BotSetting`/`BotText` tables directly and signals the bot via Redis `settings:dirty`/
`texts:dirty` flags (picked up by `jobs/sync_settings.py`).

**Build status & remaining work → see `ROADMAP.md`** (Done log + Now/Next/Backlog). This
section keeps only the *stable* design spec (stack, theme, menu, UX rules) — what's already
shipped and what's next lives in ROADMAP so it doesn't cost tokens every session.

**Stack (agreed):**
- **Backend: FastAPI** (a separate service beside the bot, sharing the same DB/Redis and **the same adapter layer in §6**). Fully async and same family as the current code; Pydantic + auto OpenAPI; JWT; PasarGuard/Guardino are also FastAPI. Tortoise via `tortoise.contrib.fastapi`.
- **Frontend: React + TypeScript + Vite + Refine + Ant Design.** CRUD-heavy panel (users, orders, panels, services, resellers) is fast with Refine (data/auth providers + RBAC); Ant Design has ready tables/forms/dashboards and **built-in RTL** for Persian. State via TanStack Query.
- **Theme target** (captured from the `Dashboard-Example-Theme-UI/` mockup so it never needs re-reading): RTL Persian, **Vazirmatn** UI font + **IBM Plex Mono** for numerals, **Material Symbols Rounded** icons, **emerald/green accent**, **dark + light** themes (CSS-var/oklch palette with green/red/amber/blue/violet status colors), layout = fixed **sidebar (~266px, grouped nav) + sticky topbar (title, search, lang + theme toggles, notifications) + card grid**. Must be **fully responsive** (sidebar → drawer on mobile). Map these onto the AntD `ConfigProvider` theme tokens.
- **Auth:** JWT (access + refresh); role from `User.Role`. In Guardino multi-tenant mode, reseller web login can also validate against Guardino Hub.
- **Deploy:** new services (`api` + built frontend behind nginx or served by the api) added to `docker-compose`, same DB/Redis. Bot and web panel share one source of truth (models + adapters).
- **Lighter alternative:** if the user prefers, the existing aiohttp + jinja2 path is possible; final call is the user's.
- **Bilingual: Persian + English** (Persian is the default, since the bot targets Persian users). RTL for Persian (Ant Design `ConfigProvider` + i18n, e.g. react-i18next); all UI strings translatable, no hard-coded copy.

**Coverage requirement (agreed — scoped, do NOT explode):** the admin panel must be complete, tidy, and extensible. "Complete" means everything needed to **manage the bot and sell** is manageable from the panel: bot management, service sales, users, orders, payments, resellers, services, servers/panels, links, nodes/groups, reports, and settings. It must cover what's needed for the **Marzban, PasarGuard, and Guardino Hub** paths **through the same adapter layer**. Anything available in the Telegram bot for a user/admin/reseller should also be available in the web panel, more structured and controllable.
**The goal is NOT to re-create upstream panels like Guardino Hub from scratch** — only to fully cover the sales/management/support/reporting/day-to-day operations of the bot.

**Suggested menu structure:**

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

**UX rules:**
- Per user/subscription: a detail page with tabs `Overview`, `Links`, `Orders`, `Payments`, `Panel Status`, `Logs`.
- Dangerous ops (delete, refund, reset usage, revoke link) require a confirmation modal; payment/balance ops stay idempotent.
- Resellers get a simpler menu with strict data scoping (only their own `parent` subtree); they must NOT see panel credentials, global bot settings, or system-wide reports.
- Guardino-specific settings (**Link Policy**, **Low Balance Thresholds**) live under Settings/Panels, not inside user pages. PasarGuard `Groups`/`proxy_settings` live on the service/panel page.
- Dashboard is a concise summary: today's sales, successful/failed orders, active users, Guardino reseller balance, panel errors, job status.
- Keep an **audit log** of admin/reseller actions; offer a read-only **"view as reseller"** for support.

**Shared principles:**
- Keep web-panel code separate from Telegram handlers: `app/web/` or `app/api/` (web/API), `app/services/` (shared business logic), `app/panels/` (adapters).
- Role separation: super_user / admin / reseller (and user where needed).
- Never leak secrets/panel tokens/payment creds/bot token/DB details in web responses.
- Reuse the same Tortoise models and panel layer (§6); don't duplicate logic.

---

## 10) Payment & financial safety

Be very careful with anything touching user/reseller balance, invoice, transaction, gateway, payment callback, order state, purchase/renew, refund, and failed payments.

- Don't rewrite financial history without an explicit request.
- Don't create duplicate transactions/invoices.
- Payment callbacks must be **idempotent**; a callback arriving twice must not double-credit.
- Never show gateway secrets or raw gateway errors to the user.

---

## 11) Bot, secrets & env safety

- Never show internal errors/traces to the Telegram user.
- **Never log:** bot token, payment token, panel token, `DATABASE_URL`, private user data, credentials, API keys.
- Keep sensitive values encrypted in DB (`PasswordField`).
- Mind: admin/reseller-only commands, force-join, callback-query authorization, FSM/Redis state, jobs, payment confirmation, proxy renew/reset/delete actions. Preserve existing conversation flow when editing a handler unless a redesign is requested.
- Don't commit secrets. Never expose: `.env`/`.env.*`, `BOT_TOKEN`, `DATABASE_URL`, `SECRET_KEY_STRING`, gateway creds, Marzban/PasarGuard tokens, Guardino API key, Redis/MariaDB creds.
- Keep sample files (`.env.example`, `.env.*.example`) committed. New env → register in `config.py` and `.env.example` with an empty/safe value (no real value).

---

## 12) Production data safety

The project may deploy with real users, resellers, payments, and panel servers.

- Don't make changes that could accidentally delete, reset, overwrite, duplicate, detach, or corrupt production data (especially users, resellers, proxies, services, servers, payments, invoices, transactions, migrations, Redis state, Docker volumes, deploy scripts).
- For sensitive production changes, recommend a backup first.
- Don't run backup/migration/reset/cleanup/update/destructive commands on production unless explicitly asked.

---

## 13) Coding conventions

- **async/await** everywhere; no blocking sync calls in handlers/jobs/views.
- Keep Telegram handlers on I/O; business logic in services/helpers; panel API logic inside adapters; gateway logic inside payment modules.
- User strings are **Persian**, mostly in `app/utils/texts.py` (reloadable from Redis); runtime settings in `app/utils/settings.py`.
- Keyboards in `app/keyboards/` mirror `handlers/`; add the matching keyboard when you add a handler.
- Admin handlers register via `*_command` + docstring for auto-help (`generate_commands_help`).
- Money is stored in **toman**, volume in **bytes**.
- Handle panel errors via `PanelError`/`PanelAuthError` (+ `status_code`) (retry pattern for 409 in `purchase.py`).
- Don't hand-edit generated code; don't log sensitive data.

---

## 14) Git

- The user usually commits manually via VS Code Source Control.
- You may inspect status/diff, but **no commit/push/tag/branch change** unless explicitly asked.
- Before suggesting a commit: `git diff --check` and `git status --short`; then summarize changed files and propose a message.
- Don't auto-run: `git commit`, `git push`, `git tag`, `git checkout`, `git switch`, `git branch`.

---

## 15) Commands & workflow (all gated by §1)

```bash
docker compose up -d --build               # run (production-like)
docker compose -f docker-compose.debug.yml up   # dev/debug
aerich migrate && aerich upgrade           # migration
make generate-client                       # regenerate Marzban client
make tag && make push                      # release (CI builds image on tag v*.*.*)
```

Version in `app/__init__.py` (`__version__`). CI: `.github/workflows/` pushes the image to ghcr.io on a `v*.*.*` tag.

**Server install** — `installer/guardinobot.sh` (menu: install/update/logs/backup/restart/status/uninstall):

```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardinobot.sh)
```

Clones the source to `/opt/GuardinoBot/src` and **builds locally** (independent of the ghcr image); `.env` + `docker-compose.yml` live in `/opt/GuardinoBot`, data in `/var/lib/guardinobot`. Migrations apply on start via `aerich upgrade`.

---

## 16) Before finishing a change

Report: what changed, what was checked, what was **not** checked, whether a migration is needed, whether a Docker rebuild is needed, whether manual/full testing is still required.

- Model changed → create a migration and announce it.
- New env → `config.py` + `.env.example`.
- New dependency → `requirements.txt` (pinned) + announce rebuild need.
- Keep multi-panel points behind the interface; don't import `marzban_client` in new code.
- If you didn't run a full build, say so honestly. Prefer small backward-compatible changes over large mixed ones.
- Don't invent details; check the repo first. When unsure about architecture/migration/Docker/payment/panel, ask first.

---

## 17) Known bugs & improvement backlog

**The live backlog (phases, status, todo, decisions) lives in `ROADMAP.md`** — read it when
you pick up a roadmap item. Don't grow the list here.

**Broadcast [resolved]:** the non-blocking worker is built (`app/utils/broadcast.py` — throttled,
`TelegramRetryAfter` sleep-retry, Redis progress + `resume_pending`, marks `blocked_bot`). Compose/
start stays bot-only (`/broadcast` + `/forward`, reply → command); the web has read-only monitor/
cancel (owner decided against a web composer). See ROADMAP for the current top items (crypto gateways:
Plisio added, NowPayments IPN security fixed; offline gateway; web gateway-config; admin glass buttons).

**Payment safety reminder (§10):** all crypto IPNs MUST verify the provider signature **mandatorily**
(no secret → reject — a missing check is a self-credit forgery hole). Balance credits on
`transaction.status = finished` via `Sum("amount")`, so never mark finished on an under/over-paid
("mismatch") callback — flag it for manual review instead.
