"""Periodic DB backup → the reports group's 🤖 backup topic.

A light tick runs every 10 minutes and produces a dump only when
``backup_interval_hours`` (settings, 0=off) has elapsed since the last one
(timestamp in Redis — also naturally staggers multiple bots sharing one
MariaDB). MySQL/MariaDB is dumped with ``mysqldump`` (mariadb-client in the
image); a sqlite DATABASE_URL is copied directly. The gzipped dump is sent as a
document; failures are reported as text in the same topic (once per interval,
because the timestamp is set before dumping).
"""

import asyncio
import gzip
import os
import time
from datetime import datetime as dt
from urllib.parse import unquote, urlparse

from aiogram.types import BufferedInputFile
from jdatetime import datetime as jdt
from pytz import timezone

import config
from app.jobs import logger
from app.main import redis, scheduler
from app.utils import helpers, settings

_LAST_TS_KEY = "reports:backup:last_ts"
_TG_DOC_LIMIT = 49 * 1024 * 1024  # Bot API sendDocument cap is 50MB — stay under
TEHRAN = timezone("Asia/Tehran")


async def _dump_database() -> tuple[bytes | None, str]:
    """(gzipped dump bytes, error text). Bytes None => failed/unsupported."""
    url = urlparse(config.DATABASE_URL)
    scheme = (url.scheme or "").lower()

    if scheme.startswith("sqlite"):
        path = (url.netloc + url.path).lstrip("/") or url.path
        try:
            with open(path, "rb") as f:
                return gzip.compress(f.read()), ""
        except OSError as exc:
            return None, f"sqlite read failed: {exc}"

    if not scheme.startswith(("mysql", "mariadb", "asyncmy")):
        return None, f"unsupported DATABASE_URL scheme: {scheme}"

    dbname = url.path.lstrip("/")
    args = [
        "mysqldump",
        "-h",
        url.hostname or "localhost",
        "-P",
        str(url.port or 3306),
        "-u",
        unquote(url.username or ""),
        "--single-transaction",
        "--quick",
        "--no-tablespaces",
        dbname,
    ]
    env = {**os.environ, "MYSQL_PWD": unquote(url.password or "")}
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        out, err = await proc.communicate()
    except FileNotFoundError:
        return None, "mysqldump not found (image must include mariadb-client)"
    if proc.returncode != 0:
        # stderr may echo connection details — keep only the first line, masked.
        first = (err or b"").decode(errors="replace").splitlines()
        return None, f"mysqldump exited {proc.returncode}: {first[0] if first else ''}"
    return gzip.compress(out), ""


async def backup_tick() -> None:
    """Scheduled gate: run a backup when the configured interval has elapsed."""
    from app.utils import reports

    _settings = settings.get_settings()
    interval = _settings.backup_interval_hours
    if (
        not interval
        or not reports.group_configured()
        or not reports.topic_enabled(reports.ReportTopic.backup)
    ):
        return

    last = float(await redis.get(_LAST_TS_KEY) or 0)
    now = time.time()
    if now - last < interval * 3600 - 90:  # 90s slack so ticks don't drift a slot
        return
    await run_backup()


async def run_backup() -> None:
    """Dump + send one backup now (used by the tick above and by the web
    panel's "backup now" action). Requires a configured group; marks the
    last-run timestamp BEFORE dumping so a failing dump alerts once per
    interval, not on every tick."""
    from app.utils import reports

    if not reports.group_configured():
        return
    await redis.set(_LAST_TS_KEY, time.time())

    data, error = await _dump_database()
    if data is None:
        logger.error("backup failed: %s", error)
        reports.report(
            reports.ReportTopic.backup,
            f"⚠️ تهیه بکاپ ناموفق بود!\n<code>{reports.sanitize(error)[:300]}</code>",
        )
        return
    if len(data) > _TG_DOC_LIMIT:
        reports.report(
            reports.ReportTopic.backup,
            "⚠️ حجم بکاپ از سقف ارسال تلگرام (50MB) بیشتر است — "
            f"({helpers.hr_size(len(data), lang='fa')}). لطفاً از بکاپ سرور (installer) استفاده کنید.",
        )
        return

    filename = f"backup_{dt.now(TEHRAN):%Y-%m-%d_%H%M}.sql.gz"
    caption = (
        "🤖 بکاپ خودکار دیتابیس ربات\n"
        f"🗓 {jdt.now(tz=TEHRAN).strftime('%Y/%m/%d - %H:%M')}\n"
        f"📦 حجم: {helpers.hr_size(len(data), lang='fa')}"
    )
    reports.report(
        reports.ReportTopic.backup,
        caption,
        document=BufferedInputFile(data, filename=filename),
    )
    logger.info("backup queued (%d bytes gz)", len(data))


scheduler.add_job(
    backup_tick,
    "interval",
    minutes=10,
    id="backup_report_tick",
    replace_existing=True,
)
