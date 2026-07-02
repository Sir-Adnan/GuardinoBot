"""Nightly summary → the reports group's 🌙 topic, 00:15 Tehran time.

Runs just after midnight and reports the PREVIOUS Tehran day (a complete
24h window): purchases/renews/reserves (PurchaseLog), sold traffic, received
money per payment method (finished Transactions), test accounts, new users,
top buyers and a per-server breakdown. No-op when the reports group is not
configured or the nightly switch is off (``force=True`` — the web panel's
"run now" — skips the switch, not the group requirement).
"""

from datetime import datetime as dt
from datetime import timedelta as td

from jdatetime import datetime as jdt
from pytz import timezone
from tortoise.expressions import Q
from tortoise.functions import Count, Sum

from app.jobs import logger
from app.main import scheduler
from app.models.proxy import Proxy, PurchaseLog
from app.models.user import Transaction, User
from app.utils import helpers, settings

TEHRAN = timezone("Asia/Tehran")

_TYPE_TITLES = {
    PurchaseLog.Type.purchase: "🛍 خرید",
    PurchaseLog.Type.renew: "♻️ تمدید",
    PurchaseLog.Type.reserve: "📦 رزرو پشتیبان",
}


def _report_range(force: bool) -> tuple[dt, dt, str]:
    """(start, end, jalali-date-label) as aware datetimes matching the
    UTC-stored created_at. Scheduled run (00:15) → the previous FULL Tehran
    day; forced run (web "run now") → TODAY so far, otherwise a manual test
    right after midnight would show an empty/stale day."""
    now_tehran = dt.now(TEHRAN)
    midnight = TEHRAN.localize(
        dt(now_tehran.year, now_tehran.month, now_tehran.day)
    )
    if force:
        start, end = midnight, now_tehran
        date_fa = (
            jdt.fromgregorian(datetime=start).strftime("%Y/%m/%d")
            + f" (تا {now_tehran.strftime('%H:%M')})"
        )
    else:
        start, end = midnight - td(days=1), midnight
        date_fa = jdt.fromgregorian(datetime=start).strftime("%Y/%m/%d")
    return start.astimezone(timezone("UTC")), end.astimezone(timezone("UTC")), date_fa


async def nightly_report(force: bool = False) -> None:
    from app.utils import reports

    _settings = settings.get_settings()
    if not reports.group_configured():
        return
    if not _settings.nightly_report_enabled and not force:
        return

    start, end, date_fa = _report_range(force)
    in_day = Q(created_at__gte=start) & Q(created_at__lt=end)

    # --- orders (PurchaseLog) -------------------------------------------------
    order_rows = (
        await PurchaseLog.filter(in_day)
        .annotate(cnt=Count("id"), total=Sum("amount"), volume=Sum("data"))
        .group_by("type")
        .values("type", "cnt", "total", "volume")
    )
    orders_by_type = {row["type"]: row for row in order_rows}
    total_volume = sum(int(row["volume"] or 0) for row in order_rows)

    # --- money received (finished transactions, by payment method) -------------
    trx_rows = (
        await Transaction.filter(
            in_day, status=Transaction.Status.finished
        )
        .annotate(cnt=Count("id"), total=Sum("amount"), gift=Sum("amount_free_given"))
        .group_by("type")
        .values("type", "cnt", "total", "gift")
    )
    total_received = sum(int(row["total"] or 0) for row in trx_rows)
    total_gift = sum(int(row["gift"] or 0) for row in trx_rows)

    # --- rejected / failed money (audit: what was turned away, not credited) ----
    rejected_rows = (
        await Transaction.filter(
            in_day,
            status__in=[Transaction.Status.rejected, Transaction.Status.failed],
        )
        .annotate(cnt=Count("id"), total=Sum("amount"))
        .group_by("type")
        .values("cnt", "total")
    )
    rejected_count = sum(int(row["cnt"] or 0) for row in rejected_rows)
    rejected_total = sum(int(row["total"] or 0) for row in rejected_rows)

    # --- counters ---------------------------------------------------------------
    test_count = await Proxy.filter(in_day, service__is_test_service=True).count()
    new_users = await User.filter(in_day).count()
    total_users = await User.all().count()

    # --- top buyers ---------------------------------------------------------------
    top_rows = (
        await PurchaseLog.filter(in_day, amount__gt=0)
        .annotate(total=Sum("amount"))
        .group_by("user_id")
        .order_by("-total")
        .limit(5)
        .values("user_id", "total")
    )

    # --- per-server breakdown ----------------------------------------------------
    server_rows = (
        # proxy_id (FK column): `proxy__isnull` resolves INTO the Proxy model
        # and raises FieldError on Tortoise 0.20
        await PurchaseLog.filter(in_day, proxy_id__isnull=False)
        .annotate(cnt=Count("id"), total=Sum("amount"), volume=Sum("data"))
        .group_by("proxy__server__name", "proxy__server__host")
        .values(
            "proxy__server__name", "proxy__server__host", "cnt", "total", "volume"
        )
    )

    orders_count = sum(int(row["cnt"] or 0) for row in order_rows)
    orders_total = sum(int(row["total"] or 0) for row in order_rows)

    lines = [
        f"🌙 <b>گزارش روزانه ربات</b> — <code>{date_fa}</code>",
        "",
        "📦 <b>سفارش‌ها</b>",
    ]
    for ptype, title in _TYPE_TITLES.items():
        row = orders_by_type.get(ptype.value) or orders_by_type.get(ptype) or {}
        lines.append(
            f"{title}: <b>{int(row.get('cnt') or 0)}</b> عدد — "
            f"<b>{int(row.get('total') or 0):,}</b> تومان"
        )
    lines += [
        f"➕ جمع سفارش‌ها: <b>{orders_count}</b> عدد — <b>{orders_total:,}</b> تومان",
        f"🖥 حجم فروخته‌شده: <b>{helpers.hr_size(total_volume, lang='fa') if total_volume else '۰'}</b>",
        "",
        "💳 <b>دریافتی به تفکیک روش پرداخت</b>",
    ]
    if trx_rows:
        for row in trx_rows:
            try:
                type_label = helpers.PAYMENT_TYPE_FA.get(
                    Transaction.PaymentType(row["type"]), str(row["type"])
                )
            except ValueError:
                type_label = str(row["type"])
            lines.append(
                f"— {type_label}: <b>{int(row['total'] or 0):,}</b> تومان "
                f"({int(row['cnt'] or 0)} تراکنش)"
            )
        lines.append(f"💰 جمع کل دریافتی: <b>{total_received:,}</b> تومان")
        if total_gift:
            lines.append(f"🎁 هدیه اعمال‌شده: <b>{total_gift:,}</b> تومان")
    else:
        lines.append("— پرداخت تأییدشده‌ای در این بازه ثبت نشده است.")
    if rejected_count:
        lines.append(
            f"🚫 ردشده/ناموفق: <b>{rejected_count}</b> تراکنش — "
            f"<b>{rejected_total:,}</b> تومان"
        )

    lines += [
        "",
        "👥 <b>کاربران</b>",
        f"🎉 جدید: <b>{new_users}</b> نفر · کل: <b>{total_users}</b> نفر",
        f"🔑 اکانت تست: <b>{test_count}</b> عدد",
    ]

    if top_rows:
        lines += ["", "🏆 <b>خریداران برتر:</b>"]
        for i, row in enumerate(top_rows, start=1):
            lines.append(
                f"{i}. <a href='tg://user?id={row['user_id']}'>{row['user_id']}</a>"
                f" — <b>{int(row['total'] or 0):,}</b> تومان"
            )

    if server_rows:
        lines += ["", "🖥 <b>سرورها:</b>"]
        for row in server_rows:
            name = row.get("proxy__server__name") or row.get("proxy__server__host") or "-"
            volume = int(row.get("volume") or 0)
            lines.append(
                f"— <b>{name}</b>: {int(row['cnt'] or 0)} سفارش، "
                f"<b>{int(row['total'] or 0):,}</b> تومان"
                + (f"، {helpers.hr_size(volume, lang='fa')}" if volume else "")
            )

    reports.report(reports.ReportTopic.nightly, "\n".join(lines), pin=True)
    logger.info("nightly report queued")


scheduler.add_job(
    nightly_report,
    "cron",
    hour=0,
    minute=15,
    timezone=TEHRAN,
    id="nightly_report",
    replace_existing=True,
)
