# Multi-bot on one server

Run many fully-isolated GuardinoBot instances on a single VPS. One shared **platform**
(MariaDB + Redis + Caddy + phpMyAdmin) serves N **per-bot app stacks** (bot · api · webpanel),
each with its own database, its own Redis logical DB, its own `.env`/token, and its own HTTPS
subdomain. No bot can see another's data; backup/restore is per-bot.

Installer/manager: **`installer/guardino.sh`** (CLI: `guardino`). The old single-install
`installer/guardinobot.sh` stays for legacy installs and as the **migration source**.

## Why it works with no core code change

The app is already env-driven: `DATABASE_URL`, `REDIS_HOST/PORT/REDIS_DB`, `BOT_TOKEN`,
`WEBHOOK_BASE_URL`/`PUBLIC_BASE_URL`, `SUPER_USERS`, `SECRET_KEY_STRING`, `WEB_JWT_SECRET`. Telegram
is **polling** (no inbound webhook to route), each bot migrates its own DB on start
(`prestart.sh` → `aerich upgrade`), and the scheduler re-registers its jobs on start — so **MariaDB
is the only authoritative state and Redis is rebuildable**. Isolation:

- **DB:** separate database + least-privilege user per bot (no grant to other DBs).
- **Redis:** separate `REDIS_DB` index per bot → isolated FSM/scheduler/cache/broadcast keyspace.
- **Webhooks/IPN/panel/reports:** per-bot subdomain + per-bot api/webpanel reading only its own DB/Redis.

## One-time setup

1. **DNS:** point a **wildcard** record `*.<base>` → your server IP (e.g. `*.bots.example.com`).
   Open ports 80 + 443 (Caddy issues HTTPS automatically).
2. Install + init the platform:
   ```bash
   bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino.sh) install
   # set the base domain when asked (e.g. bots.example.com)
   ```

## Day-to-day

```bash
guardino add <name>            # create a bot → https://<name>.<base>/ (prompts token + super-admins)
guardino list                  # all bots (domain, db, redis-db)
guardino update [name|all]     # git pull + rebuild the shared image ONCE, restart instance(s)
guardino logs <name> [service] # service = bot (default) | api | webpanel
guardino restart|stop|start <name>
guardino status
guardino edit-env <name>       # then: guardino restart <name>
guardino remove <name>         # stop; optionally DROP its DB + backups
guardino domain                # change the base domain
```

## Backup & restore (per-bot or all)

State = MariaDB (Redis is rebuildable). A backup = the bot's `mysqldump` + its `.env` + compose + meta.

```bash
guardino backup <name>          # → /var/lib/guardino/backups/<name>/guardino-<name>-<ts>.tar.gz
guardino backup all             # every bot (+ a platform-env snapshot for full DR)
guardino restore <name> <file>  # recreate ONE bot independently (DB + user + import + up)
```

- **Restore a single bot** without touching the others: `guardino restore bot3 <file>`.
- **Full disaster recovery** (server died): reinstall the platform, then `restore` each bot tarball.
- Retention: the last 10 backups per bot are kept.

## Migrating an existing single install

```bash
guardino migrate-legacy [name]   # default name: main
```
Dumps the legacy DB (`/opt/GuardinoBot`), imports it into the shared MariaDB, and carries the legacy
`.env` **wholesale** (keeps `SECRET_KEY_STRING` — required to decrypt stored panel passwords — plus
`BOT_TOKEN`/`SUPER_USERS`/`WEB_JWT_SECRET`), repointing only `DATABASE_URL`/`REDIS_DB`/domain. You can
**keep the legacy domain** for this bot so existing gateway IPN URLs stay valid. **Verify** the new bot
(panel login decrypts secrets, bot polls, a test IPN arrives) **before** stopping the old stack; the old
`/var/lib/guardinobot` is left intact as a safety net.

## Limits & notes

- **Up to 64 bots per Redis** (logical DB indices 0–63). For more, add a second Redis or another server.
- Shared MariaDB is tuned with `--max-connections=500`; each bot has `mem_limit`s. The shared DB/Redis
  are the only shared components — back up the platform and keep an eye on resources.
- A **base domain is required** (per-bot HTTPS subdomain) — payment gateways need an HTTPS callback.
- phpMyAdmin is bound to `127.0.0.1:8081`; reach it over an SSH tunnel
  (`ssh -L 8081:localhost:8081 root@<server>`).
- No DB migration and **no core code change** — only the installer. `update` rebuilds the shared image
  once; each bot re-runs `aerich upgrade` on its own DB at start.
