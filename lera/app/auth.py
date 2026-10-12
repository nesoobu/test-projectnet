import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from . import config

MAX_AGE = 7 * 24 * 3600


def validate_init_data(init_data: str, token: str = config.BOT_TOKEN) -> dict | None:
    """Проверка подписи Telegram WebApp initData. Возвращает user + start_param или None."""
    if not init_data or not token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    if time.time() - int(pairs.get("auth_date", 0) or 0) > MAX_AGE:
        return None
    try:
        user = json.loads(pairs.get("user", "{}"))
    except ValueError:
        return None
    if not user.get("id"):
        return None
    user["start_param"] = pairs.get("start_param")
    return user
