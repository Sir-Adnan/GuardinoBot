import asyncio
from datetime import datetime as dt
from datetime import timedelta as td

from app.jobs import logger
from app.main import redis, scheduler
from app.utils import settings, texts

# Set by the web-panel API after a settings / texts write.
SETTINGS_DIRTY_KEY = "settings:dirty"  # app/api/routers/settings.py
TEXTS_DIRTY_KEY = "texts:dirty"  # app/api/routers/texts.py
ALERTS_RUN_KEY = "alerts:run_now"  # app/api/routers/automation.py (run-now button)
REPORTS_ACTIONS_KEY = "reports:web:actions"  # reports-group test/run-now queue


async def _process_reports_actions() -> None:
    """Drain web-panel reports-group actions (test message / nightly / backup).
    They must run in the BOT process — the API can't reach the reports
    pipeline (separate process, no app.main)."""
    import json

    from app.utils import reports

    for _ in range(10):  # bounded drain per tick
        raw = await redis.lpop(REPORTS_ACTIONS_KEY)
        if not raw:
            break
        try:
            item = json.loads(raw)
            action = item.get("action")
        except (ValueError, TypeError):
            continue
        if action == "test_topic":
            try:
                topic = reports.ReportTopic(item.get("topic"))
            except ValueError:
                continue
            reports.report(
                topic,
                f"🧪 پیام تست تاپیک «{reports.TOPIC_TITLES[topic]}»\n"
                "این پیام از وب‌پنل برای بررسی سلامت گزارش‌دهی ارسال شد. ✅",
            )
            logger.info("reports test message queued for %s", topic.value)
        elif action == "nightly":
            from app.jobs.nightly_report import nightly_report  # local: no cycle

            # awaited (not a bare create_task): a query failure must show up
            # in the log instead of vanishing with the GC'd task
            try:
                await nightly_report(force=True)
                logger.info("nightly report sent (web run-now)")
            except Exception:  # noqa: BLE001
                logger.error("nightly report (web run-now) failed", exc_info=True)
        elif action == "backup":
            from app.jobs.backup_report import run_backup  # local: no cycle

            task = asyncio.create_task(run_backup())
            task.add_done_callback(
                lambda t: t.cancelled()
                or not t.exception()
                or logger.error("backup (web run-now) failed", exc_info=t.exception())
            )
            logger.info("backup triggered (web run-now)")


async def _safe(coro, name: str) -> None:
    """Isolate one sync step: a persistent failure in one stage (e.g. a
    blocked outbound HTTP call in a gateway auto-check) must not starve the
    stages after it on every tick."""
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        logger.error("sync_settings step '%s' failed: %s", name, exc)


async def sync_settings() -> None:
    """Reload the in-process settings/texts caches when the web panel changed
    them (the API sets a Redis flag). Cheap poll — keeps the bot in sync without
    a restart, since the API runs in a separate process and can't touch the
    bot's cached ``_settings`` / ``_texts``. Also picks up a web "run alerts now"
    request and fires the (forced) alert scan in the background."""
    try:
        if await redis.get(SETTINGS_DIRTY_KEY):
            await redis.delete(SETTINGS_DIRTY_KEY)
            await settings.reload_settings()
            logger.info("settings reloaded (web-panel change)")
        if await redis.get(TEXTS_DIRTY_KEY):
            await redis.delete(TEXTS_DIRTY_KEY)
            await texts.reload_texts()
            logger.info("texts reloaded (web-panel change)")
        if await redis.get(ALERTS_RUN_KEY):
            await redis.delete(ALERTS_RUN_KEY)
            from app.jobs.proxy_alerts import proxy_alerts  # local: avoid cycle

            # background task so a full scan never blocks this 15s poll loop
            asyncio.create_task(proxy_alerts(force=True))
            logger.info("proxy_alerts triggered (web run-now)")

        # interactive web actions first — they must never be starved by the
        # payment checkers below
        await _safe(_process_reports_actions(), "reports_actions")

        # drain any web-submitted offline-payment reviews (credit runs here so
        # user-notify + service-activation work in the bot process)
        from app.main import bot  # local: avoid import-order issues
        from app.plugins.payment.offline.handlers import (
            process_offline_review_queue,
        )
        from app.plugins.payment.crypto.plisio_service import (
            auto_check_plisio_payments,
            process_plisio_review_queue,
        )
        from app.plugins.payment.crypto.nowpayments_service import (
            auto_check_nowpayments_payments,
            process_nowpayments_review_queue,
        )

        await _safe(process_offline_review_queue(bot), "offline_reviews")
        await _safe(process_plisio_review_queue(), "plisio_reviews")
        await _safe(process_nowpayments_review_queue(), "nowpayments_reviews")
        await _safe(auto_check_plisio_payments(), "plisio_auto_check")
        await _safe(auto_check_nowpayments_payments(), "nowpayments_auto_check")
    except Exception as exc:  # noqa: BLE001
        logger.error("sync_settings failed: %s", exc)


scheduler.add_job(
    sync_settings,
    "interval",
    seconds=15,
    id="sync_settings",
    replace_existing=True,
    start_date=dt.now() + td(seconds=15),
)
