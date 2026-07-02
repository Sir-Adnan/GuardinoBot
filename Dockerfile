FROM python:3.11.10-alpine

LABEL org.opencontainers.image.title="Guardino-Bot" \
      org.opencontainers.image.description="Telegram subscription-sales bot (Marzban / PasarGuard / Guardino Hub)" \
      org.opencontainers.image.source="https://github.com/Sir-Adnan/GuardinoBot" \
      org.opencontainers.image.authors="UnknownZero"

COPY ./requirements.txt /app/

WORKDIR /app

# mariadb-client: mysqldump for the in-bot backup job (app/jobs/backup_report.py).
# Non-fatal on purpose: alpine mirrors are often unreachable from IR servers and
# a failed apk must not kill the whole update — the backup job detects the
# missing mysqldump at runtime and reports it in the backup topic instead.
RUN apk add --no-cache mariadb-client || \
    echo "WARN: mariadb-client install failed; backup-to-topic disabled"

RUN pip install -r requirements.txt

COPY . /app

RUN chmod +x bot.py
RUN chmod +x prestart.sh

ENV PYTHONUNBUFFERED=1

# JSON/exec form (no "JSONArgsRecommended" warning); `exec` makes bot.py the
# main process so SIGTERM on `docker stop`/restart reaches it → clean on_shutdown.
CMD ["sh", "-c", "./prestart.sh && exec ./bot.py"]
