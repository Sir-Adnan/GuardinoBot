import random
from datetime import UTC
from datetime import datetime as dt
from datetime import timedelta as td
from typing import TYPE_CHECKING, Literal

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise.functions import Count, Sum

from app.keyboards.premium import premium_button
from app.keyboards.user import account
from app.models.user import RialGatewayPayment, Transaction
from app.utils import buttons as _b

if TYPE_CHECKING:
    from app.utils import settings


def get_payment_variables(
    method: str, _settings: "settings.Settings"
) -> tuple[int, int, int]:
    for k, v in _settings.payment_plugins().items():
        if method == k:
            _st = getattr(_settings, v)
            return _st.min_pay_amount, _st.free_after, _st.free_after_percent
    raise ValueError(f"Settings for payment method {method!r} not found")


async def choose_auto_select_method(
    _settings: "settings.Settings",
    algorithm: str = None,
) -> str | None:
    _s = _settings.payment_auto_select
    if not _s.enabled:
        return None

    ps = _s.payment_methods

    algorithm = (
        _settings.payment_auto_select.algorithm.value if not algorithm else algorithm
    )

    if algorithm == "random":
        while ps:
            p = random.choice(ps)
            _p = getattr(_settings, p)
            if _p.enabled:
                return p
            ps.remove(p)
    else:
        if _s._cached_provider and (  # five minute cache of selected provider
            (_s._cached_provider_timestamp + 500) > dt.now(UTC).timestamp()
        ):
            print("using cache", _s._cached_provider)
            return _s._cached_provider
        q = (
            RialGatewayPayment.filter(
                transaction__status=Transaction.Status.finished,
                transaction__finished_at__gt=dt.now(UTC) - td(days=_s.duration),
            )
            .annotate(
                count=Count("provider"),
            )
            .group_by("provider")
        )
        if algorithm == "least_vol":
            q = (
                q.annotate(total=Sum("transaction__amount"))
                .order_by("total")
                .values_list("provider", flat=True)
            )
        elif algorithm == "most_vol":
            q = (
                q.annotate(total=Sum("transaction__amount"))
                .order_by("-total")
                .values_list("provider", flat=True)
            )
        elif algorithm == "least_count":
            q = (
                q.annotate(count=Count("provider"))
                .order_by("count")
                .values_list("provider", flat=True)
            )
        elif algorithm == "most_count":
            q = (
                q.annotate(count=Count("provider"))
                .order_by("-count")
                .values_list("provider", flat=True)
            )
        result = await q
        if result:
            result = f"payment_{result[0].value}"
            _s._cached_provider = result
            _s._cached_provider_timestamp = dt.now(UTC).timestamp()
            return result
    # fallback to random if no value returned from algorithms
    return await choose_auto_select_method(_settings=_settings, algorithm="random")


class MinAmountValueError(Exception):
    def __init__(self, *args: object, min_amount: int) -> None:
        self.min_amount = min_amount
        super().__init__(*args)


class ChargePanel(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="slctpmm"):
        method: str

    class DirectCallback(CallbackData, prefix="paypdirsrv"):
        amount: int
        service_id: int
        menu_id: int = 0
        proxy_id: int = 0
        current_page: int = 0
        mode: Literal["purchase", "renew", "reserve"] = "purchase"

    def __init__(
        self,
        _settings: "settings.Settings",
        amount: int = 0,
        service_id: int = 0,
        menu_id: int = 0,
        proxy_id: int = 0,
        direct_mode: Literal["purchase", "renew", "reserve"] | None = None,
        back_callback: CallbackData | None = None,
        auto_select_plugin: str = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        min_amount = None
        any_added = False
        plugins = _settings.payment_plugins()

        plugins_to_skip = []

        for _, p in plugins.items():
            if p in plugins_to_skip:
                continue
            plugin = getattr(_settings, p)
            menu_title = plugin.menu_title
            if plugin.enabled:
                if p == "payment_auto_select":
                    plugins_to_skip = plugin.payment_methods
                    plugin = getattr(_settings, auto_select_plugin)
                if amount:
                    if plugin.is_voucher:
                        continue
                    if amount < plugin.min_pay_amount:
                        if min_amount is None or plugin.min_pay_amount < min_amount:
                            min_amount = plugin.min_pay_amount
                        continue
                    free = int(
                        0
                        if (not plugin.free_after) or (amount < plugin.free_after)
                        else amount * (plugin.free_after_percent / 100)
                    )
                    self.add(
                        premium_button(
                            text=menu_title
                            if not free
                            else f"{menu_title} 🔥 + {free:,} تومان",
                            key=_b.pay_method_key(plugin._name),
                            callback_data=SelectPayAmount.Callback(
                                amount=amount,
                                free=free,
                                method=plugin._name,
                                service_id=service_id,
                                menu_id=menu_id,
                                proxy_id=proxy_id,
                                direct_mode=direct_mode,
                            ),
                        )
                    )
                    any_added = True
                else:
                    self.add(
                        premium_button(
                            text=menu_title,
                            key=_b.pay_method_key(plugin._name),
                            callback_data=self.Callback(
                                method=plugin._name,
                            ),
                        )
                    )
                    any_added = True
        if not any_added and min_amount is not None:
            raise MinAmountValueError(
                f"Minimum amount value reached for {amount}. min_amount={min_amount}",
                min_amount=min_amount,
            )

        if back_callback:
            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=back_callback,
                )
            )

        self.adjust(1, 1, 1)


class SelectPayAmount(InlineKeyboardBuilder):
    class Callback(CallbackData, prefix="payslctam"):
        amount: int
        free: int = 0
        method: str
        service_id: int = 0
        menu_id: int = 0
        proxy_id: int = 0
        direct_mode: Literal["purchase", "renew", "reserve"] | None = None

    def __init__(
        self,
        method: str,
        _settings: "settings.Settings",
        is_verified: bool = True,
        back_callback: CallbackData | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if is_verified:
            amount_list = _settings.charge_amount_list
            orders = _settings.charge_amount_orders
            min_pay_amount, free_after, free_after_percent = get_payment_variables(
                method=method, _settings=_settings
            )
            for amount in amount_list:
                if amount < min_pay_amount:
                    continue
                free = int(
                    0
                    if (not free_after) or (amount < free_after)
                    else amount * (free_after_percent / 100)
                )
                self.button(
                    text=(
                        f"{amount:,} تومان"
                        if not free
                        else f"{free:,} 🔥 + {amount:,} تومان"
                    ),
                    callback_data=self.Callback(
                        amount=amount,
                        free=free,
                        method=method,
                    ),
                )
            self.add(
                premium_button(
                    text="✍️ مبلغ دلخواه",
                    key="pay_custom_amount",
                    callback_data=self.Callback(amount=0, method=method),
                )
            )

            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=account.UserPanel.Callback(
                        action=account.UserPanelAction.charge
                    ),
                )
            )
            while sum(orders) > len(amount_list):
                if orders[-1] <= 1:
                    orders.pop()
                else:
                    orders[-1] -= 1

            self.adjust(*orders, 1, 1)
        else:
            self.add(
                premium_button(
                    text="🔙 برگشت",
                    key="common_back",
                    callback_data=back_callback
                    if back_callback
                    else account.UserPanel.Callback(
                        action=account.UserPanelAction.charge
                    ),
                )
            )
