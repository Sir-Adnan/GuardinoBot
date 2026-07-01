# Architecture — directory map, data models, commands

> Reference detail. CLAUDE.md has the stack table + entry point + a high-level tree; read this
> for the full map / models / command list. Don't assume the map is complete — search before changing.

Entry: `bot.py` → `app/main.py:main()`.
Startup order: DB → webapp → plugins → routers → middlewares → API servers → scheduler → `run_polling`.

## Directory map

```text
app/
  main.py            # bootstrap: bot, dp, redis, scheduler
  marzban.py         # legacy registry (Marzban.servers) + setup_api; also refreshes PanelRegistry on startup
  panels/            # ★ neutral adapter layer (docs/panels.md): base, marzban, pasarguard, guardino, registry
  api/               # ★ FastAPI WEB-PANEL backend (docs/webpanel.md): routers/ (dashboard, users, services,
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
webpanel/            # ★ React+TS+Vite+Refine+AntD web panel frontend (docs/webpanel.md) — src/{pages,components,...}
marzban_client/      # ❗ auto-generated — do not hand-edit (docs/panels.md)
migrations/models/   # aerich migrations
docs/references/upstream-apis/  # vendor API specs (NOWPayments/Plisio/Marzban/PasarGuard/Guardino) — heavy, parse don't read whole
scripts/             # import/migrate + backup
config.py            # reads env + TORTOISE_ORM
```

## Data models (key)

- **User** — roles in `User.Role`: `user(0)`, `reseller(1)`, `admin(2)`, `super_user(3)`. Reseller tree (parent/child), referrer, balance/postpaid, `UserSetting`.
- **Server** — panel connection: `host`, `port`, `https`, `token`, `username/password` (encrypted), `is_enabled`, `total_proxies`, **`panel_type`** (enum `marzban`/`pasarguard`/`guardino`, default `marzban`), and **`link_policy`** (enum `master_first`/`node_first` — Guardino only, which sub link to show).
- **Service / ServiceMenu** — plans: `data_limit`, `expire_duration`, `inbounds` (Marzban: protocol→tags), `flow`, `price`, discount, nested menus, filters; and **`panel_config`** (JSON nullable — PasarGuard: `{"group_ids":[...], "proxy_settings":{...}}`; Guardino: `{"total_gb", "days"|"duration_preset", "node_ids"|"node_group", "pricing_mode"}`).
- **Proxy** — a user's subscription on a Server; unique `username`, `status` (ProxyStatus == PanelUserStatus values), `service`, `user`, `server`, `reserve`; for id-based panels (Guardino): **`panel_user_id`** (int, hub user id) + **`sub_token`** (master_sub_token).
- **Invoice / Transaction (+payment subtypes) / Discount / Reserve / PurchaseLog**.

User balance is **computed** (`User.get_balance` = sum of finished transactions minus non-draft invoices), not a stored raw value.

> Panel migrations are additive: `46_*` (`Server.panel_type` + `Service.panel_config`) and `47_*` (`Server.link_policy`, widen `Server.username`→64, `Proxy.panel_user_id` + `Proxy.sub_token`). Applied automatically on container start (`prestart.sh` → `aerich upgrade`); the installer/update path does the same.

## Commands & workflow (all gated by the "never auto-run" rule in CLAUDE.md)

```bash
docker compose up -d --build               # run (production-like)
docker compose -f docker-compose.debug.yml up   # dev/debug
aerich migrate && aerich upgrade           # migration
make generate-client                       # regenerate Marzban client
make tag && make push                      # release (CI builds image on tag v*.*.*)
```

Version in `app/__init__.py` (`__version__`). CI: `.github/workflows/` pushes the image to ghcr.io on a `v*.*.*` tag.

**Server install (many bots on one server)** — `installer/guardino-bot.sh` (CLI `guardino-bot`): one
shared platform (MariaDB + Redis + Caddy + phpMyAdmin) + an isolated app stack per bot (own DB + own
`REDIS_DB` + own HTTPS subdomain), with per-bot backup/restore.

```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino-bot.sh)
```

The installer uses the `guardino-bot` namespace everywhere (`/opt/guardino-bot`,
`/var/lib/guardino-bot`, `guardino-bot-net`, `guardino-bot-platform`) so it does not collide with
Guardino Hub. **Full guide → `docs/multi-bot.md`.** No core code change — it only generates
per-instance compose/.env/Caddy (the app is already env-driven; Telegram is polling).
