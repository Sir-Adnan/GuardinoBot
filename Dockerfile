FROM python:3.11.10-alpine

LABEL org.opencontainers.image.title="Guardino-Bot" \
      org.opencontainers.image.description="Telegram subscription-sales bot (Marzban / PasarGuard / Guardino Hub)" \
      org.opencontainers.image.source="https://github.com/Sir-Adnan/GuardinoBot" \
      org.opencontainers.image.authors="UnknownZero"

COPY ./requirements.txt /app/

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app

RUN chmod +x bot.py
RUN chmod +x prestart.sh

ENV PYTHONUNBUFFERED=1

# JSON/exec form (no "JSONArgsRecommended" warning); `exec` makes bot.py the
# main process so SIGTERM on `docker stop`/restart reaches it → clean on_shutdown.
CMD ["sh", "-c", "./prestart.sh && exec ./bot.py"]
