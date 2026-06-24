# GuardinoBot

A Telegram bot for selling proxy/VPN subscriptions, with a multi-panel backend.

- **Panels:** Marzban (legacy, kept stable) + **PasarGuard** and **Guardino Hub** (active development).
- **Stack:** Python 3.11 · aiogram 3 (polling) · Tortoise ORM + aerich · MariaDB · Redis · APScheduler · aiohttp · Docker.
- **Repo:** <https://github.com/Sir-Adnan/GuardinoBot> · **Author:** UnknownZero.

## Install (server)

```bash
bash <(curl -Ls --ipv4 https://raw.githubusercontent.com/Sir-Adnan/GuardinoBot/main/installer/guardinobot.sh)
```

The installer sets up Docker, generates `docker-compose.yml` + `.env`, builds the image locally, and starts the bot. A `guardinobot` management command is installed with a menu: **install · update · logs · backup · restart · status · edit config · uninstall**.

- App dir: `/opt/GuardinoBot` · Data: `/var/lib/guardinobot`
- DB migrations are applied automatically on start (`aerich upgrade`).

## Manual run

```bash
cp .env.example .env      # fill BOT_TOKEN, SUPER_USERS, WEBHOOK_BASE_URL, DATABASE_URL, SECRET_KEY_STRING
docker compose up -d --build
```

## License

Proprietary. All rights reserved.
