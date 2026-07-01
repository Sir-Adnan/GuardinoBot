"""Low-balance alerts for Guardino-hub reseller wallets.

Guardino bills the bot owner's reseller wallet inside the hub on every create/
renew. If that wallet runs dry, sales fail. This job periodically reads each
Guardino server's reseller balance and warns the super-users on two thresholds
(configurable in settings): a soft warn and a stronger critical warn.

Anti-spam: we only message when severity gets *worse* than the last alerted
level (stored per server in Redis); recovery updates the stored level silently.
"""

from app.jobs import logger
from app.main import redis, scheduler
from app.models.server import Server
from app.panels import PanelError
from app.panels.registry import PanelRegistry
from app.utils import settings

_SEV = {"ok": 0, "warn": 1, "critical": 2}


async def check_hub_balances() -> None:
    _settings = settings.get_settings()
    warn = _settings.guardino_balance_warn
    critical = _settings.guardino_balance_critical

    for server in await Server.filter(is_enabled=True).all():
        panel = PanelRegistry.try_get(server.id)
        if panel is None or not getattr(panel, "panel_managed_billing", False):
            continue  # Guardino-only
        try:
            balance = await panel.get_balance()
        except PanelError as exc:
            logger.warning(
                f"hub balance check failed for server {server.id}: {exc.status_code}"
            )
            continue
        except Exception as exc:  # noqa: BLE001 - never let one server break the job
            logger.warning(f"hub balance check error for server {server.id}: {exc}")
            continue

        level = (
            "critical" if balance < critical else ("warn" if balance < warn else "ok")
        )
        key = f"guardino:balance:alerted:{server.id}"
        prev = await redis.get(key)
        if isinstance(prev, bytes):
            prev = prev.decode()
        prev = prev or "ok"

        if _SEV[level] > _SEV.get(prev, 0):
            if level == "critical":
                text = (
                    "🚨 هشدار جدی موجودی گاردینو هاب\n"
                    f"سرور: <b>{server.identifier}</b>\n"
                    f"موجودی فعلی: <b>{balance:,}</b> تومان\n\n"
                    f"موجودی به زیر {critical:,} تومان رسید! امکان اختلال در فروش/تمدید وجود دارد — لطفاً فوراً شارژ کنید."
                )
            else:
                text = (
                    "⚠️ هشدار موجودی گاردینو هاب\n"
                    f"سرور: <b>{server.identifier}</b>\n"
                    f"موجودی فعلی: <b>{balance:,}</b> تومان\n\n"
                    f"موجودی به زیر {warn:,} تومان رسید؛ لطفاً به‌موقع شارژ کنید."
                )
            from app.utils import reports

            reports.report(
                reports.ReportTopic.misc, text, legacy_super_users=True
            )
            logger.info(
                f"hub balance alert ({level}) sent for server {server.id}: {balance}"
            )

        if level != prev:
            await redis.set(key, level)


scheduler.add_job(
    check_hub_balances,
    "interval",
    minutes=30,
    id="check_hub_balances",
    replace_existing=True,
)
