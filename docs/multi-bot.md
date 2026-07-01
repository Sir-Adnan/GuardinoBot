# Multi-bot On One Server

Run many fully isolated Guardino-Bot instances on one VPS. One shared platform
(MariaDB + Redis + Caddy + phpMyAdmin) serves per-bot app stacks (`bot`, `api`,
`webpanel`). Each bot has its own database, Redis logical DB, `.env`, token, and
HTTPS subdomain.

Installer/manager: `installer/guardino-bot.sh`

CLI command: `guardino-bot`

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
```

## Backup And Restore

```bash
guardino-bot backup <name>
guardino-bot backup all
guardino-bot restore <name> <file>
guardino-bot backup-telegram
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
- phpMyAdmin is shared and bound to `127.0.0.1:8081`; use an SSH tunnel to reach it.
- Each bot runs migrations on its own database when its container starts.
