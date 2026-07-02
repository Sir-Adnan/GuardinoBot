# Multi-bot On One Server

Run many fully isolated Guardino-Bot instances on one VPS. One shared platform
(MariaDB + Redis + Caddy + phpMyAdmin) serves per-bot app stacks (`bot`, `api`,
`webpanel`). Each bot has its own database, Redis logical DB, `.env`, token, and
HTTPS subdomain.

Installer/manager: `installer/guardino-bot.sh`

CLI command: `guardino-bot`

Status: **owner-verified on a real VPS** — multiple bots installed and running end-to-end.

## One-Time Setup

1. Point a wildcard DNS record `*.<base>` to the server IP.
2. Open ports 80 and 443.
3. Install the platform:

```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardino-bot.sh) install
```

## Day To Day

```bash
guardino-bot add <name>
guardino-bot list
guardino-bot update [name|all]
guardino-bot logs <name> [bot|api|webpanel]
guardino-bot restart <name>
guardino-bot stop <name>
guardino-bot start <name>
guardino-bot status
guardino-bot edit-env <name>
guardino-bot remove <name>
guardino-bot domain
guardino-bot platform-up      # (re)start the shared platform services
guardino-bot repair-cli       # reinstall the CLI from the repo copy
guardino-bot uninstall        # remove EVERYTHING (destructive)
```

## Backup And Restore

```bash
guardino-bot backup <name>
guardino-bot backup all
guardino-bot restore <name> <file>
guardino-bot backup-send      # back up now + send to the configured Telegram bot
guardino-bot backup-telegram  # configure the scheduled Telegram backup (cron)
```

Backups are stored under:

```text
/var/lib/guardino-bot/backups/<name>/guardino-bot-<name>-<timestamp>.tar.gz
```

Scheduled Telegram backup uses:

```text
/etc/cron.d/guardino-bot-backup
/var/log/guardino-bot-backup.log
```

## Namespaces

Guardino-Bot intentionally avoids the plain `guardino` namespace so it can live
on the same server as Guardino Hub without collisions.

```text
CLI:              /usr/local/bin/guardino-bot
Root:             /opt/guardino-bot
Data:             /var/lib/guardino-bot
Docker network:   guardino-bot-net
Platform project: guardino-bot-platform
Images:           guardino-bot:local, guardino-bot-webpanel:local
Instance prefix:  guardino-bot-<name>
DB prefix:        guardino_bot_<name>
DB user prefix:   gbot_<name>
```

## Notes

- A fresh install is expected; legacy auto-migration is intentionally not part of
  this installer.
- Redis logical DBs are allocated per bot.
- **Web-panel API routing**: every instance's services join the shared
  `guardino-bot-net`, where Docker aliases each compose service by its bare name
  — so `api` resolves round-robin across ALL bots' APIs. The webpanel's nginx
  therefore proxies to `${API_UPSTREAM}` (envsubst template), and the installer
  sets it to the instance's unique container `guardino-bot-<name>-api:8000`.
  Symptoms of a wrong/bare upstream: login codes arriving from another bot,
  random 401 logouts (JWT signed by another instance).
- phpMyAdmin is shared and bound to `127.0.0.1:8081`; use an SSH tunnel to reach it.
- Each bot runs migrations on its own database when its container starts.
- All containers use `restart: unless-stopped` (except MariaDB/Redis: `always`)
  so every bot comes back automatically after a server reboot.
- `guardino-bot update` also regenerates the platform compose and the Caddyfile
  (new `WEBHOOK_PATHS` entries reach existing servers) and validates the
  Caddyfile before reloading Caddy.
- `restore` derives the database, DB user, and domain from the **target**
  instance name (like `add`) and rewrites `DATABASE_URL`/`DOMAIN` in the
  restored `.env` — restoring a backup under a new name clones the bot instead
  of attaching to the original's live database.
- `remove` (with "keep database") preserves the instance `.env` under the
  backups dir — it holds the only copy of `SECRET_KEY_STRING`.
- `stop` keeps containers (log history survives); `remove`/`uninstall` still
  use `down`.
