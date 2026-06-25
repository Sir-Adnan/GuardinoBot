from typing import Any, Callable

from pydantic import BaseModel

from app.models.setting import BotText
from app.plugins.payment.card_to_card import card_to_card
from app.plugins.payment.crypto import nowpayments, swapino
from app.plugins.payment.perfect_money import perfect_money
from app.plugins.payment.rial_gateway import aqaye_pardakht, payping, zarinpal, zibal
from app.plugins.payment.tronseller import tronado
from app.utils.values import TextValue, format_active_inbounds, format_config_links


class FormatVariables(dict):
    def __missing__(self, key):
        return key.join("{}")


class StartText(TextValue):
    value: str = """
👋 سلااااام
به ربات خوش اومدی😉

با سرویس‌های ما میتونی همیشه و هر لحظه و با هر دستگاهی به اینترنت متصل بمونی🌝

💡 برای دریافت اخبار، وضعیت سرویس‌ها و دریافت کدهای هدیه روزانه در کانال ما عضو بشید
🆔 @GuardinoBot

🔍 اگه میخوای بیشتر در مورد ربات بدونی میتونی دکمه <b>«راهنما»</b> رو بزنی
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class MainMenuText(TextValue):
    value: str = """
♻️ منوی اصلی ربات:
🤖 چه کاری میتونم براتون انجام بدم؟👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class ForceJoinText(TextValue):
    value: str = """
♻️ برای استفاده از ربات باید در کانال ما عضو بشید

توی کانالی که پایین مشخص شده عضو بشید و سپس دکمه «تأیید عضویت» رو بزنید👇

🆔 @GuardinoBot
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class SupportText(TextValue):
    value: str = """
✋ به بخش پشتیبانی خوش اومدی

قبل از اینکه به پشتیبانی پیام بدید، حواستون باشه که بخش‌ «راهنما» رو مطالعه کرده باشید، احتمالا جواب سوالتون رو پیدا می‌کنید😉

⁉️ جواب سوالتون اونجا نبود؟ اشکالی نداره، میتونید از طریق آیدی زیر با پشتیبانی ارتباط برقرار کنید👇

🆔 @username

💡 بعد از پیام دادن به پشتیبانی، لطفا صبور باشید. به همه پیام‌ها در اسرع وقت جواب داده میشه🙏
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class PurchaseText(TextValue):
    value: str = """
📲 در حال حاضر سرویس‌های زیر برای خرید موجود هستند:👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class HelpText(TextValue):
    value: str = """
به بخش راهنمای استفاده از ربات خوش اومدید

شما می‌تونید برای خرید اشتراک به چند روش پرداخت رو انجام بدید که می‌تونید با کلیک رو دکمه «شارژ حساب» اون‌ها رو ببینید. 
😃 آموزش استفاده از هرکدوم از روش‌ها رو هم اونجا براتون گذاشتیم! 

بعد از اینکه حسابتون رو شارژ کردید، میتونید روی دکمه «خرید اشتراک» کلیک کنید و پلن مناسب خودتون رو خریداری کنید و به صورت آنی تحویل بگیرید. به همین سادگی😇

برای دیدن اشتراک‌هایی که قبلا خریداری کردید کافیه روی دکمه «اشتراک‌های من» کلیک کنید🙃
توی این قسمت لیست تمام اشتراک‌های شما بهتون نشون داده میشه. برای دیدن اطلاعات و مدیریت هر کدوم از اون‌ها میتونید روش کلیک کنید و وارد بخش تنظیماتش بشید😉

برای اینکه بدونی چقدر موجودی داری میتونی روی دکمه «اطلاعات حساب» کلیک کنی و اطلاعات بیشتر رو اونجا ببینی🤓

همچنین میتونید با استفاده از دعوت بقیه به ربات، اعتبار هدیه بگیرید😋

💡یک سری سوالات متوالی که ممکنه براتون پیش بیاد رو هم توی کانالمون قرار دادیم که میتونید از این لینک مطلاعه کنید🙋:
<a href='https://t.me'>❔ سوالات متدوال</a>

اگه جواب سوالتون رو در این بخش یا بخش سوالات متداول پیدا نکردید، میتونید از طریق دکمه «پشتیبانی» با پشتیبانی ربات تماس بگیرید. خوشحال میشیم سوالاتتون رو جواب بدیم و مشکلاتتون رو حل کنیم🤗

📞 اگر فروشنده هستید و قصد خرید تعداد بالا دارید، با پشتیبانی تماس بگیرید تا سطح اکانت شما ارتقا پیدا کنه و قابلیت‌های مخصوص فروشندگان براتون فعال بشه🤫
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class CommandNotFoundText(TextValue):
    value: str = """
🤕 متوجه دستور ارسالی نشدم!
برای رفتن به منوی اصلی دستور /menu رو ارسال کنید😉
    """
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class ProxyHelpText(TextValue):
    value: str = """
🔑 پروکسی های فعال: {ACTIVE_INBOUNDS}

🔗 لینک اتصال هوشمند: 
<code>{SUBSCRIPTION_URL}</code>

❕برای اطلاع یافتن از وضعیت پروکسی بدون وارد شدن به ربات، میتونید لینک اتصال هوشمند رو ذخیره کنید و در مروگر باز کنید، یا اینکه روی لینک زیر کلیک کنید:
<a href='{SUBSCRIPTION_URL}'>🔺 اتصال هوشمند</a>

💡 برای دریافت راهنمای اتصال و استفاده دستور /help را ارسال کنید!
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "SUBSCRIPTION_URL": lambda v: v,
        "ACTIVE_INBOUNDS": format_active_inbounds,
        "CONFIG_LINKS": format_config_links,
    }


class ReferralBannerText(TextValue):
    value: str = """
سلام ✋
با این ربات میتونی خیلی راحت و ارزون فیلترشکن اختصاصی بخری 🤤
اگه میخوای از شر قطعی و سرعت کم فیلترشکنا راحت شی همین الان وارد ربات زیر شو👇👇👇

{INVITE_LINK}
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "INVITE_LINK": lambda v: v,
    }


class ChargeText(TextValue):
    value: str = """
♻️ شما میتونید به روش‌های مختلفی حسابتون رو شارژ کنید🙄

برای ادامه مراحل شارژ حساب، یکی از روش‌های پرداخت زیر رو انتخاب کنید👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class VerifyPhoneNumber(TextValue):
    value: str = """
⚠️ برای استفاده از ربات باید شماره موبایل خود را تأیید کنید!

برای تأیید شماره موبایل روی دکمه زیر کلیک کنید👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {}


class AlertExpiryText(TextValue):
    value: str = """
⏳ <b>یادآوری تمدید</b>

سرویس <b>{NAME}</b> رو‌ به اتمامه — فقط <b>{DAYS_LEFT} روز</b> دیگه باقی مونده! ⌛️

برای اینکه اتصالت بدون وقفه ادامه پیدا کنه، همین حالا تمدیدش کن 👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "NAME": lambda v: v,
        "DAYS_LEFT": lambda v: v,
    }


class AlertLowDataText(TextValue):
    value: str = """
📉 <b>حجمت رو به اتمامه</b>

از سرویس <b>{NAME}</b> فقط حدود <b>{DATA_LEFT}</b> حجم باقی مونده!

برای جلوگیری از قطع شدن اتصال، همین حالا تمدید کن یا حجم بگیر 👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "NAME": lambda v: v,
        "DATA_LEFT": lambda v: v,
    }


class AlertUnusedText(TextValue):
    value: str = """
👋 سلام!

دیدیم که هنوز از سرویس <b>{NAME}</b> استفاده نکردی 🤔

اگه در اتصال مشکلی داری، راهنمای اتصال رو ببین یا به پشتیبانی پیام بده — ما همیشه کنارتیم تا راحت وصل شی 💚
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "NAME": lambda v: v,
    }


class AlertEndedText(TextValue):
    value: str = """
🔴 <b>اشتراکت به پایان رسید</b>

سرویس <b>{NAME}</b> به پایان رسید (حجم یا زمانش تموم شد) و اتصالت قطع شده.

برای ادامهٔ اتصالِ بی‌دردسر، همین حالا دوباره تمدیدش کن 👇
"""
    _allowed_variables: dict[str, Callable[[Any], str]] = {
        "NAME": lambda v: v,
    }


class Texts(BaseModel):
    class Config:
        from_attributes = True

    @classmethod
    def format(cls, text: TextValue, **kwargs):
        allowed: dict[str, tuple[str, Callable[[Any], str]]] = {}
        for key, value in kwargs.items():
            if key in text._allowed_variables:
                allowed[key] = (value, text._allowed_variables.get(key))

        if (
            "AMOUNT_RIAL" in text._allowed_variables
            and allowed.get("AMOUNT_RIAL") is None
            and allowed.get("AMOUNT_TOMAN") is not None
        ):
            allowed["AMOUNT_RIAL"] = (
                allowed["AMOUNT_TOMAN"][0] * 10,
                text._allowed_variables.get("AMOUNT_RIAL"),
            )
        if (
            "AMOUNT_DOLLARS" in text._allowed_variables
            and allowed.get("AMOUNT_DOLLARS") is None
            and allowed.get("AMOUNT_TOMAN") is not None
            and allowed.get("USDT_RATE") is not None
        ):
            allowed["AMOUNT_DOLLARS"] = (
                allowed["USDT_RATE"][0] * allowed["AMOUNT_TOMAN"],
                text._allowed_variables.get("AMOUNT_DOLLARS"),
            )

        return text.value.format_map(
            FormatVariables({k: v[1](v[0]) for k, v in allowed.items()})
        )

    start: StartText = StartText()
    main_menu: MainMenuText = MainMenuText()
    force_join: ForceJoinText = ForceJoinText()
    purchase: PurchaseText = PurchaseText()
    support: SupportText = SupportText()
    help: HelpText = HelpText()
    command_not_found: CommandNotFoundText = CommandNotFoundText()

    proxy_help: ProxyHelpText = ProxyHelpText()

    referral_banner_text: ReferralBannerText = ReferralBannerText()

    charge: ChargeText = ChargeText()

    verify_phone_number: VerifyPhoneNumber = VerifyPhoneNumber()

    # user notification / proxy alerts (jobs/proxy_alerts.py)
    alert_expiry: AlertExpiryText = AlertExpiryText()
    alert_low_data: AlertLowDataText = AlertLowDataText()
    alert_unused: AlertUnusedText = AlertUnusedText()
    alert_ended: AlertEndedText = AlertEndedText()

    # payment crypto
    payment_nowpayments: nowpayments.Texts = nowpayments.Texts()
    payment_swapino: swapino.Texts = swapino.Texts()

    payment_card_to_card: card_to_card.Texts = card_to_card.Texts()
    payment_perfect_money: perfect_money.Texts = perfect_money.Texts()

    # payment rial gateway
    payment_payping: payping.Texts = payping.Texts()
    payment_aqaye_pardakht: aqaye_pardakht.Texts = aqaye_pardakht.Texts()
    payment_zibal: zibal.Texts = zibal.Texts()
    payment_zarinpal: zarinpal.Texts = zarinpal.Texts()

    # payment tronseller
    payment_tronado: tronado.Texts = tronado.Texts()

    @classmethod
    async def from_db(cls) -> "Texts":
        defualt = {key: val.default for key, val in cls.model_fields.items()}
        texts = await BotText.get_or_create(default=defualt)
        update_dict: dict[str, str] = dict()
        for name, value in texts.items():
            if (name in {**cls.model_fields}) and (
                value is None or value.strip() == ""
            ):
                update_dict[name] = cls.model_fields[name].default

        if update_dict:
            await BotText.update(**update_dict)
            texts = await BotText.get_or_create(default=defualt)
        return cls.model_validate(texts)

    @classmethod
    async def update(cls, **kwargs: dict[str, Any]):
        # validate new values based on model type annotations
        # serialized = dict()
        # for k, v in kwargs.items():
        #     cls.__pydantic_validator__.validate_assignment(cls.model_construct(), k, v)
        #     serialized[k] = to_jsonable_python(
        #         v
        #     )  # serialize to json (best option for saving char in db)
        return await BotText.update(**kwargs)


_texts = Texts()


def get_texts() -> Texts:
    return _texts


async def reload_texts() -> None:
    global _texts
    _texts = await Texts.from_db()
