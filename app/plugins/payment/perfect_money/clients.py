import re

import httpx

from app.logger import get_logger
from app.utils import settings

logger = get_logger("perfect_money")

BASE_URL = "https://perfectmoney.com/acct"


VALUE_RE = re.compile("<input name='(.*)' type='hidden' value='(.*)'>")


class PerfectMoneyError(Exception):
    pass


class PerfectMoneyAPI:
    @classmethod
    async def _call_api(cls, method: str, data: dict[str, str]):
        async with httpx.AsyncClient() as client:
            r = await client.post(url=BASE_URL.rstrip("/") + method, data=data)
            if r.status_code == 200:
                return r.text
            else:
                raise PerfectMoneyError(str(r))

    @classmethod
    async def ev_activate(cls, ev_number: str, ev_code: str):
        _settings = settings.get_settings().payment_perfect_money
        data = {
            "AccountID": _settings.account_id,
            "PassPhrase": _settings.passphrase,
            "Payee_Account": _settings.payee_account,
            "ev_number": ev_number,
            "ev_code": ev_code,
        }
        logger.debug(f"Activating Perfectmoney with data: {data}")
        resp = await cls._call_api(method="/ev_activate.asp", data=data)
        logger.debug(f"Perfectmoney result: {resp}")

        values = {}
        for match in VALUE_RE.finditer(resp):
            if match.group(1) == "ERROR":
                raise PerfectMoneyError(match.group(2))
            values.update({match.group(1): match.group(2)})
        return values
