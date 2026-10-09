"""Бизнес-логика: цены, заказы, оплаты, выдача, рефералы, рассылки, фоновые задачи."""
import asyncio
import html
import logging
import os
import re
import time
import uuid

import aiohttp
import aiosqlite
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

from . import config
from .config import ADMIN_IDS
from .db import db
from .render import base_ctx, mask, money, send_key, sys_btn

log = logging.getLogger(__name__)
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20)
EXTERNAL_METHODS = ("crypto", "yookassa", "ton")


async def http_json(method: str, url: str, **kw):
    async with aiohttp.ClientSession(timeout=kw.pop("timeout", HTTP_TIMEOUT)) as s:
        async with s.request(method, url, **kw) as r:
            return r.status, await r.json(content_type=None)


# ================= продукты и цены =================

def product_name(kind: str, qty: int, lang: str = "ru") -> str:
    if kind == "premium":
        return f"Telegram Premium {qty} {'mo.' if lang == 'en' else 'мес.'}"
    if kind == "topup":
        return "Top-up" if lang == "en" else "Пополнение"
    return f"{qty} ⭐️"


async def base_price(kind: str, qty: int) -> float | None:
    pkg = await db.one("SELECT price FROM packages WHERE kind=? AND stars=? AND enabled=1 AND price IS NOT NULL",
                       kind, qty)
    if pkg:
        return round(pkg["price"], 2)
    if kind == "stars":
        return round(qty * await db.get_float("rate"), 2)
    return None  # premium только пакетами


def parse_levels(raw: str) -> list[tuple[int, float]]:
    out = []
    for part in raw.split(","):
        if ":" in part:
            a, b = part.split(":", 1)
            try:
                out.append((int(a.strip()), float(b.strip())))
            except ValueError:
                pass
    return sorted(out)


async def user_level(uid: int) -> tuple[float, int, tuple[int, float] | None]:
    """(текущая скидка %, куплено звёзд, следующий уровень)."""
    bought = (await db.one("SELECT COALESCE(SUM(stars),0) s FROM orders WHERE user_id=? AND kind='stars' "
                           "AND status='done'", uid))["s"]
    pct, nxt = 0.0, None
    for need, p in parse_levels(await db.get("levels")):
        if bought >= need:
            pct = p
        elif nxt is None:
            nxt = (need, p)
    return pct, bought, nxt


async def promo_valid(code: str, uid: int) -> dict | None:
    p = await db.one("SELECT * FROM promos WHERE code=? COLLATE NOCASE", code)
    if not p or p["uses_left"] == 0:
        return None
    if await db.one("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", p["code"], uid):
        return None
    return p


async def fraud_check(user: dict, amount: float, recipient: str = "") -> bool:
    """True — заказ можно создавать."""
    black = {x.strip().lstrip("@").lower() for x in (await db.get("blacklist")).split(",") if x.strip()}
    if recipient and recipient.lower() in black:
        return False
    limit = await db.get_int("daily_max_orders")
    if limit:
        n = (await db.one("SELECT COUNT(*) n FROM orders WHERE user_id=? AND kind!='topup' AND created>?",
                          user["id"], int(time.time()) - 86400))["n"]
        if n >= limit:
            return False
    hours, max_amount = await db.get_int("new_user_hours"), await db.get_float("new_user_max_amount")
    if hours and max_amount and (user["created"] or 0) > time.time() - hours * 3600 and amount > max_amount:
        return False
    return True


async def create_order(user: dict, kind: str, amount: float, qty: int = 0,
                       recipient: str = "", recipient_name: str = "") -> dict:
    discount, promo, pct = 0.0, None, 0.0
    if kind in ("stars", "premium"):
        if kind == "stars":
            pct += (await user_level(user["id"]))[0]
        u = await db.user(user["id"])
        if u and u["promo"]:
            p = await promo_valid(u["promo"], user["id"])
            if p:
                promo = p["code"]
                pct += p["discount"]
            else:
                await db.run("UPDATE users SET promo=NULL WHERE id=?", user["id"])
        discount = round(amount * min(pct, 90) / 100, 2)
    now = int(time.time())
    cur = await db.run(
        "INSERT INTO orders (user_id, kind, stars, recipient, recipient_name, amount, discount, promo, status,"
        " created, updated) VALUES (?,?,?,?,?,?,?,?, 'new', ?, ?)",
        user["id"], kind, qty, recipient, recipient_name, round(amount - discount, 2), discount, promo, now, now)
    return await db.order(cur.lastrowid)


async def order_ctx(bot: Bot, order: dict) -> dict:
    user = await db.user(order["user_id"])
    ctx = await base_ctx(bot, user)
    rec = html.escape(order["recipient"] or "")
    name = html.escape(order.get("recipient_name") or "")
    ctx.update(order_id=order["id"], stars=order["stars"], months=order["stars"], recipient=rec,
               recipient_display=f"{name} (@{rec})" if name else f"@{rec}",
               recipient_masked=mask(order["recipient"]),
               product=product_name(order["kind"], order["stars"], ctx["_lang"]),
               amount=money(order["amount"]), card=html.escape(await db.get("card_details")),
               discount_line=(f"\n🎟 Скидка: <b>-{money(order['discount'])} {ctx['currency']}</b>"
                              + (f" ({html.escape(order['promo'])})" if order["promo"] else "")
                              if order["discount"] else ""),
               refund_line="", ton_wallet=html.escape(await db.get("ton_wallet")),
               ton_amount=ton_str(order.get("pay_amount")), ton_comment=ton_comment(order["id"]))
    return ctx


# ================= проверка получателя =================

async def lookup_recipient(username: str) -> tuple[bool, str]:
    """Проверка, что @username — существующий пользователь (по публичной странице t.me).
    Возвращает (существует, отображаемое имя). При ошибке сети не блокирует заказ."""
    if not await db.get_bool("check_recipient"):
        return True, ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.get(f"https://t.me/{username}", headers={"User-Agent": "Mozilla/5.0"}) as r:
                page = await r.text()
    except Exception as e:
        log.info("recipient check failed: %s", e)
        return True, ""
    title = re.search(r'<div class="tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', page, re.S)
    if not title:
        return False, ""
    extra = re.search(r'<div class="tgme_page_extra">(.*?)</div>', page, re.S)
    if extra and re.search(r"subscriber|member|подписчик|участник", extra.group(1), re.I):
        return False, ""  # канал или группа
    name = html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip()
    return True, name[:64]


# ================= курсы =================

_rates: dict = {"ts": 0}


async def market_rates() -> dict:
    """Курсы TON и USDT к фиату (CoinGecko), кэш 5 минут."""
    fiat = (await db.get("fiat_code")).lower()
    if time.time() - _rates["ts"] > 300 or _rates.get("fiat") != fiat:
        _, data = await http_json("GET", "https://api.coingecko.com/api/v3/simple/price",
                                  params={"ids": "the-open-network,tether", "vs_currencies": fiat})
        _rates.update(ts=time.time(), fiat=fiat, ton=float(data["the-open-network"][fiat]),
                      usd=float(data["tether"][fiat]))
    return _rates


async def update_auto_rate():
    if not await db.get_bool("auto_rate"):
        return
    usd = (await market_rates())["usd"]
    rate = await db.get_float("star_cost_usd") * usd * (1 + await db.get_float("markup_percent") / 100)
    if rate > 0:
        await db.set("rate", money(rate))


# ================= платёжные системы =================

async def crypto_call(method: str, **params):
    token = await db.get("cryptobot_token")
    host = "testnet-pay.crypt.bot" if await db.get_bool("cryptobot_testnet") else "pay.crypt.bot"
    _, data = await http_json("POST", f"https://{host}/api/{method}", json=params,
                              headers={"Crypto-Pay-API-Token": token})
    if not data.get("ok"):
        raise RuntimeError(f"CryptoBot {method}: {data.get('error')}")
    return data["result"]


async def crypto_invoice(order: dict) -> tuple[str, str]:
    res = await crypto_call(
        "createInvoice", currency_type="fiat", fiat=await db.get("fiat_code"),
        amount=money(order["amount"]), accepted_assets=await db.get("crypto_assets"),
        description=f"Заказ #{order['id']}", payload=str(order["id"]),
        expires_in=await db.get_int("order_ttl_min") * 60)
    return str(res["invoice_id"]), res.get("bot_invoice_url") or res.get("pay_url")


async def yk_auth():
    return aiohttp.BasicAuth(await db.get("yk_shop_id"), await db.get("yk_secret"))


async def yk_invoice(order: dict, return_url: str) -> tuple[str, str]:
    status, data = await http_json(
        "POST", "https://api.yookassa.ru/v3/payments", auth=await yk_auth(),
        headers={"Idempotence-Key": f"order-{order['id']}-{uuid.uuid4().hex[:8]}"},
        json={"amount": {"value": f"{order['amount']:.2f}", "currency": await db.get("fiat_code")},
              "capture": True, "confirmation": {"type": "redirect", "return_url": return_url},
              "description": f"Заказ #{order['id']}", "metadata": {"order_id": order["id"]}})
    if status >= 300:
        raise RuntimeError(f"YooKassa: {data}")
    return data["id"], data["confirmation"]["confirmation_url"]


def ton_comment(oid: int) -> str:
    return f"order-{oid}"


def ton_str(nano) -> str:
    try:
        return f"{int(nano) / 1e9:.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


async def ton_prepare(order: dict) -> tuple[str, str]:
    """Возвращает (сумма в нанотонах, ссылка Tonkeeper)."""
    price = (await market_rates())["ton"]
    nano = int(order["amount"] / price * 1e9)
    nano = (nano // 1_000_000 + 1) * 1_000_000  # округляем вверх до 0.001 TON
    wallet = await db.get("ton_wallet")
    url = f"https://app.tonkeeper.com/transfer/{wallet}?amount={nano}&text={ton_comment(order['id'])}"
    return str(nano), url


async def ton_incoming() -> list[dict]:
    headers = {}
    if key := await db.get("toncenter_key"):
        headers["X-API-Key"] = key
    _, data = await http_json("GET", "https://toncenter.com/api/v2/getTransactions",
                              params={"address": await db.get("ton_wallet"), "limit": 100}, headers=headers)
    return [t["in_msg"] for t in data.get("result", []) if t.get("in_msg")]


def ton_matches(order: dict, msgs: list[dict]) -> bool:
    need = int(order["pay_amount"] or 0)
    for m in msgs:
        if (m.get("message") or "").strip() == ton_comment(order["id"]) and int(m.get("value") or 0) >= need * 0.99:
            return True
    return False


async def is_paid(order: dict, ton_msgs: list[dict] | None = None) -> bool:
    m = order["method"]
    if m == "crypto":
        res = await crypto_call("getInvoices", invoice_ids=order["invoice_id"])
        items = res.get("items", [])
        return bool(items) and items[0]["status"] == "paid"
    if m == "yookassa":
        _, data = await http_json("GET", f"https://api.yookassa.ru/v3/payments/{order['invoice_id']}",
                                  auth=await yk_auth())
        return data.get("status") == "succeeded"
    if m == "ton":
        return ton_matches(order, ton_msgs if ton_msgs is not None else await ton_incoming())
    return False


async def enabled_methods() -> list[str]:
    out = []
    if await db.get_bool("pay_crypto") and await db.get("cryptobot_token"):
        out.append("crypto")
    if await db.get_bool("pay_yookassa") and await db.get("yk_shop_id") and await db.get("yk_secret"):
        out.append("yookassa")
    if await db.get_bool("pay_ton") and await db.get("ton_wallet"):
        out.append("ton")
    if await db.get_bool("pay_manual"):
        out.append("manual")
    return out


# ================= уведомления =================

async def admin_targets() -> list:
    chat = await db.get("log_chat_id")
    if chat:
        return [chat]
    ids = set(ADMIN_IDS) | {a["id"] for a in await db.all("SELECT id FROM admins")}
    return list(ids)


async def notify_admins(bot: Bot, text: str, kb: Kb | None = None):
    for t in await admin_targets():
        try:
            await bot.send_message(t, text, reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.warning("notify %s failed: %s", t, e)


def order_admin_kb(oid: int, paid: bool) -> Kb:
    rows = []
    if not paid:
        rows.append([Btn(text="✅ Оплата есть", callback_data=f"ad:op:{oid}")])
    else:
        rows.append([Btn(text="✅ Выдано", callback_data=f"ad:od:{oid}"),
                     Btn(text="🔁 Повторить API", callback_data=f"ad:or:{oid}")])
    rows.append([Btn(text="❌ Отменить" + (" + возврат" if paid else ""), callback_data=f"ad:oc:{oid}")])
    return Kb(inline_keyboard=rows)


def order_line(o: dict, cur: str = "") -> str:
    who = f"@{o['recipient']}" if o["recipient"] else ""
    what = f"{product_name(o['kind'], o['stars'])} → {who}" if o["kind"] != "topup" else "пополнение"
    return f"#{o['id']} · {what} · {money(o['amount'])}{cur} · {o['method'] or '—'} · {o['status']}"


# ================= жизненный цикл заказа =================

async def mark_paid(bot: Bot, oid: int) -> bool:
    if not await db.set_status(oid, "paid", ("new", "pending", "review")):
        return False
    order = await db.order(oid)
    if order["promo"]:
        await db.run("INSERT OR IGNORE INTO promo_uses VALUES (?, ?)", order["promo"], order["user_id"])
        await db.run("UPDATE promos SET used=used+1, uses_left=CASE WHEN uses_left>0 THEN uses_left-1 ELSE uses_left END"
                     " WHERE code=?", order["promo"])
        await db.run("UPDATE users SET promo=NULL WHERE id=?", order["user_id"])

    if order["kind"] == "topup":
        await db.add_balance(order["user_id"], order["amount"])
        await db.set_status(oid, "done")
        await send_key(bot, order["user_id"], "topup_done", await order_ctx(bot, order))
        await notify_admins(bot, f"💰 Пополнение {order_line(order)}")
        return True

    await send_key(bot, order["user_id"], "order_paid", await order_ctx(bot, order))
    await deliver(bot, oid)
    return True


async def deliver(bot: Bot, oid: int):
    order = await db.order(oid)
    mode = await db.get("delivery_mode")
    if mode == "fragment" or (mode == "api" and await db.get("delivery_api_url")):
        if mode == "fragment":
            ok, err, retry = await _deliver_fragment(order)
        else:
            (ok, err), retry = await _deliver_api(order), True
        if ok:
            await complete(bot, oid)
            return
        max_tries = max(await db.get_int("delivery_retries"), 1)
        # retry=False — повтор опасен (могли уже заплатить) или бессмыслен: сразу к админу
        attempts = order["attempts"] + 1 if retry else max_tries
        await db.run("UPDATE orders SET attempts=?, next_try=? WHERE id=?",
                     attempts, int(time.time()) + 60 * 2 ** (attempts - 1), oid)
        await db.set_status(oid, "failed")
        if attempts >= max_tries:
            hint = "" if retry else "\n❗️ Автоповтор отключён: проверьте на fragment.com, прошла ли покупка."
            await notify_admins(bot, f"⚠️ <b>Автовыдача не удалась</b>\n{order_line(order)}\n"
                                     f"<code>{html.escape(err)}</code>{hint}", order_admin_kb(oid, paid=True))
        return
    await notify_admins(bot, f"🆕 <b>Выдайте товар</b>\n{order_line(order)}", order_admin_kb(oid, paid=True))


# ================= выдача через Fragment (библиотека fragment-api-py) =================

_fragment_lock = asyncio.Lock()  # покупки строго по одной: у кошелька общий seqno


def fragment_client():
    from FragmentAPI import FragmentClient  # pip install fragment-api-py
    return FragmentClient(cookies=config.FRAGMENT_COOKIES or None, seed=config.FRAGMENT_SEED,
                          api_key=config.FRAGMENT_API_KEY, api_provider=config.FRAGMENT_API_PROVIDER,
                          wallet_version=config.FRAGMENT_WALLET_VERSION)


async def _deliver_fragment(order: dict) -> tuple[bool, str, bool]:
    """Покупка на Fragment с TON-кошелька магазина. Возвращает (успех, ошибка, можно ли повторять)."""
    if not (config.FRAGMENT_SEED and config.FRAGMENT_API_KEY):
        return False, "В .env не заданы FRAGMENT_SEED и FRAGMENT_API_KEY", False
    try:
        from FragmentAPI import exceptions as fx
    except ImportError:
        return False, "Библиотека не установлена: pip install fragment-api-py", False
    async with _fragment_lock:
        try:
            async with fragment_client() as fc:
                if order["kind"] == "premium":
                    res = await fc.purchase_premium(order["recipient"], order["stars"],
                                                    show_sender=False, payment_method="ton")
                else:
                    res = await fc.purchase_stars(order["recipient"], order["stars"],
                                                  show_sender=False, payment_method="ton")
        except (fx.BroadcastUncertainError, fx.ConfirmationTimeout) as e:
            return False, f"Транзакция отправлена, но результат неизвестен: {e}", False
        except fx.UserNotFoundError as e:
            return False, f"Получатель не найден на Fragment: {e}", False
        except (fx.ConfigurationError, fx.CookieError) as e:
            return False, f"Ошибка настроек Fragment: {e}", False
        except Exception as e:
            return False, f"{type(e).__name__}: {e}", True  # до отправки транзакции — можно повторить
    if getattr(res, "confirmed", False):
        log.info("fragment #%s ok tx=%s", order["id"], getattr(res, "transaction_id", ""))
        return True, "", False
    tx = getattr(res, "transaction_id", None)
    if tx:
        return False, f"Транзакция {tx} отправлена, Fragment не подтвердил: {res.confirmation_error}", False
    return False, "Кошелёк не подключён (проверьте FRAGMENT_SEED)", False


async def fragment_wallet() -> tuple[str, float]:
    async with fragment_client() as fc:
        w = await fc.get_wallet()
    return w.address, w.gram_balance


async def _deliver_api(order: dict) -> tuple[bool, str]:
    """Универсальный вызов Fragment-провайдера.
    POST {url} JSON {type, username, quantity, months, order_id}, заголовок Authorization: Bearer <key>.
    Адаптируйте под своего провайдера при необходимости."""
    url, key = await db.get("delivery_api_url"), await db.get("delivery_api_key")
    payload = {"type": order["kind"], "username": order["recipient"], "order_id": order["id"]}
    payload["months" if order["kind"] == "premium" else "quantity"] = order["stars"]
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
            async with s.post(url, json=payload, headers={"Authorization": f"Bearer {key}"}) as r:
                body = await r.text()
                if r.status != 200:
                    return False, f"HTTP {r.status}: {body[:300]}"
                try:
                    data = await r.json(content_type=None)
                except Exception:
                    data = {}
                if isinstance(data, dict) and data.get("ok") is False:
                    return False, body[:300]
                return True, ""
    except Exception as e:
        return False, repr(e)


async def complete(bot: Bot, oid: int) -> bool:
    if not await db.set_status(oid, "done", ("paid", "failed")):
        return False
    order = await db.order(oid)
    user = await db.user(order["user_id"])
    # реферальные: 2 уровня
    ref1 = user["ref_id"] if user else None
    ref2 = (await db.user(ref1) or {}).get("ref_id") if ref1 else None
    for ref, key in ((ref1, "ref_percent"), (ref2, "ref_percent2")):
        if ref and ref != order["user_id"]:
            bonus = round(order["amount"] * await db.get_float(key) / 100, 2)
            if bonus > 0:
                await db.add_balance(ref, bonus)
                await db.run("UPDATE users SET ref_earned=ROUND(ref_earned+?, 2) WHERE id=?", bonus, ref)
    ctx = await order_ctx(bot, order)
    await send_key(bot, order["user_id"], "order_done", ctx)
    await notify_admins(bot, f"✅ Выполнен {order_line(order)}")
    if channel := await db.get("autopost_channel"):
        try:
            await send_key(bot, channel, "autopost", {**ctx, "_lang": (await db.languages())[0]})
        except Exception as e:
            log.warning("autopost: %s", e)
    if await db.get("reviews_channel"):
        rows = [[Btn(text="⭐️" * n, callback_data=f"rv:{oid}:{n}") for n in (1, 2, 3)],
                [Btn(text="⭐️" * n, callback_data=f"rv:{oid}:{n}") for n in (4, 5)]]
        try:
            await send_key(bot, order["user_id"], "review_ask", ctx, top=rows)
        except Exception:
            pass
    return True


async def cancel(bot: Bot, oid: int, notify_user: bool = True) -> bool:
    order = await db.order(oid)
    if not order or order["status"] in ("done", "canceled"):
        return False
    was_paid = order["status"] in ("paid", "failed")
    if not await db.set_status(oid, "canceled", (order["status"],)):
        return False
    ctx = await order_ctx(bot, order)
    if was_paid and order["kind"] != "topup":
        await db.add_balance(order["user_id"], order["amount"])
        ctx["refund_line"] = f"\n💰 {money(order['amount'])} {ctx['currency']} → баланс."
    if notify_user:
        try:
            await send_key(bot, order["user_id"], "order_canceled", ctx)
        except Exception:
            pass
    return True


# ================= рефералы: вывод =================

async def withdraw_available(user: dict) -> float:
    return max(0.0, round(min(user["balance"], user["ref_earned"] - user["withdrawn"]), 2))


async def withdraw_create(bot: Bot, user: dict, amount: float, details: str) -> int | None:
    if amount > await withdraw_available(await db.user(user["id"])) or not await db.take_balance(user["id"], amount):
        return None
    await db.run("UPDATE users SET withdrawn=ROUND(withdrawn+?, 2) WHERE id=?", amount, user["id"])
    cur = await db.run("INSERT INTO withdrawals (user_id, amount, details, status, created) VALUES (?,?,?, 'new', ?)",
                       user["id"], amount, details, int(time.time()))
    wid = cur.lastrowid
    who = f"@{user['username']}" if user["username"] else str(user["id"])
    await notify_admins(bot, f"💸 <b>Вывод #{wid}</b>\n{html.escape(who)} (<code>{user['id']}</code>)\n"
                             f"Сумма: {money(amount)}\nРеквизиты: <code>{html.escape(details)}</code>",
                        Kb(inline_keyboard=[[Btn(text="✅ Выплачено", callback_data=f"ad:wdok:{wid}"),
                                             Btn(text="❌ Отклонить", callback_data=f"ad:wdno:{wid}")]]))
    return wid


async def withdraw_finish(bot: Bot, wid: int, ok: bool) -> bool:
    cur = await db.run("UPDATE withdrawals SET status=? WHERE id=? AND status='new'", "done" if ok else "rejected", wid)
    if cur.rowcount == 0:
        return False
    w = await db.one("SELECT * FROM withdrawals WHERE id=?", wid)
    if not ok:
        await db.add_balance(w["user_id"], w["amount"])
        await db.run("UPDATE users SET withdrawn=ROUND(withdrawn-?, 2) WHERE id=?", w["amount"], w["user_id"])
    ctx = await base_ctx(bot, await db.user(w["user_id"]))
    ctx.update(wid=wid, amount=money(w["amount"]))
    try:
        await send_key(bot, w["user_id"], "withdraw_done" if ok else "withdraw_rejected", ctx)
    except Exception:
        pass
    return True


# ================= рассылки =================

SEGMENTS = {
    "all": "Все",
    "buyers": "Покупатели",
    "nonbuyers": "Без покупок",
    "inactive": "Неактивные 30+ дней",
    "abandoned": "Бросили заказ (7 дней)",
}


async def segment_query(segment: str) -> tuple[str, list]:
    now = int(time.time())
    done = "SELECT user_id FROM orders WHERE status='done' AND kind IN ('stars','premium')"
    base = "SELECT id FROM users WHERE banned=0"
    if segment == "buyers":
        return f"{base} AND id IN ({done})", []
    if segment == "nonbuyers":
        return f"{base} AND id NOT IN ({done})", []
    if segment == "inactive":
        return f"{base} AND COALESCE(last_seen, created) < ?", [now - 30 * 86400]
    if segment == "abandoned":
        return (f"{base} AND id IN (SELECT user_id FROM orders WHERE kind IN ('stars','premium') AND created>? "
                f"AND status IN ('new','pending','canceled')) AND id NOT IN ({done} AND created>?)",
                [now - 7 * 86400, now - 7 * 86400])
    if segment.startswith("lang_"):
        lang = segment[5:]
        if lang == (await db.languages())[0]:
            return f"{base} AND (lang=? OR lang IS NULL)", [lang]
        return f"{base} AND lang=?", [lang]
    return base, []


async def segment_count(segment: str) -> int:
    q, a = await segment_query(segment)
    return (await db.one(f"SELECT COUNT(*) n FROM ({q})", *a))["n"]


async def run_broadcast(bot: Bot, bid: int):
    b = await db.one("SELECT * FROM broadcasts WHERE id=?", bid)
    if not b or not (await db.run("UPDATE broadcasts SET status='running' WHERE id=? AND status='scheduled'", bid)).rowcount:
        return
    q, a = await segment_query(b["segment"])
    ok = fail = 0
    for u in await db.all(q, *a):
        try:
            await bot.copy_message(u["id"], b["chat_id"], b["msg_id"])
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # ~20 сообщений/сек — в пределах лимитов Telegram
    await db.run("UPDATE broadcasts SET status='done', ok=?, fail=? WHERE id=?", ok, fail, bid)
    try:
        await bot.send_message(b["admin_id"], f"📢 Рассылка #{bid} завершена: ✅ {ok}, ❌ {fail}")
    except Exception:
        pass


# ================= бэкап =================

async def backup(bot: Bot, chat_id) -> None:
    path = f"{db.path}.backup"
    async with aiosqlite.connect(path) as dst:
        await db.conn.backup(dst)
    try:
        await bot.send_document(chat_id, FSInputFile(path, filename=f"backup-{time.strftime('%Y%m%d-%H%M')}.db"),
                                caption="💾 Бэкап базы")
    finally:
        os.remove(path)


# ================= фоновые задачи =================

_last_run: dict[str, float] = {}
_low_balance_alerted = 0.0


def _due(name: str, every: float) -> bool:
    now = time.time()
    if now - _last_run.get(name, 0) >= every:
        _last_run[name] = now
        return True
    return False


async def _check_payments(bot: Bot):
    pending = await db.all("SELECT * FROM orders WHERE status='pending' AND method IN ('crypto','yookassa','ton')")
    ton_msgs = None
    for o in pending:
        try:
            if o["method"] == "ton" and ton_msgs is None:
                ton_msgs = await ton_incoming()
            if await is_paid(o, ton_msgs):
                await mark_paid(bot, o["id"])
        except Exception as e:
            log.warning("payment check #%s: %s", o["id"], e)


async def _retry_deliveries(bot: Bot):
    max_tries = max(await db.get_int("delivery_retries"), 1)
    for o in await db.all("SELECT id FROM orders WHERE status='failed' AND attempts<? AND next_try<=?",
                          max_tries, int(time.time())):
        if await db.set_status(o["id"], "paid", ("failed",)):
            await deliver(bot, o["id"])


async def _auto_refund(bot: Bot):
    mins = await db.get_int("auto_refund_min")
    if not mins:
        return
    for o in await db.all("SELECT * FROM orders WHERE status IN ('paid','failed') AND kind!='topup' AND updated<?",
                          int(time.time()) - mins * 60):
        if await cancel(bot, o["id"]):
            await notify_admins(bot, f"↩️ Автовозврат на баланс: {order_line(o)}")


async def _expire_and_remind(bot: Bot):
    now = int(time.time())
    ttl = await db.get_int("order_ttl_min") * 60
    for o in await db.all("SELECT id FROM orders WHERE status IN ('new','pending') AND created<?", now - ttl):
        await cancel(bot, o["id"], notify_user=False)
    remind = await db.get_int("remind_after_min")
    if not remind:
        return
    for o in await db.all("SELECT * FROM orders WHERE status IN ('new','pending') AND kind!='topup' AND reminded=0 "
                          "AND created<?", now - remind * 60):
        await db.run("UPDATE orders SET reminded=1 WHERE id=?", o["id"])
        ctx = await order_ctx(bot, o)
        try:
            await send_key(bot, o["user_id"], "reminder", ctx, top=[
                [await sys_btn("continue", ctx, callback_data=f"cont:{o['id']}")],
                [await sys_btn("cancel", ctx, callback_data=f"oc:{o['id']}")]])
        except Exception:
            pass


async def _low_balance(bot: Bot):
    global _low_balance_alerted
    limit = await db.get_float("low_balance_alert")
    url = await db.get("delivery_balance_url")
    fragment = await db.get("delivery_mode") == "fragment" and config.FRAGMENT_SEED
    if not limit or not (url or fragment):
        return
    try:
        if fragment:
            _, bal = await fragment_wallet()
        else:
            _, data = await http_json("GET", url, headers={"Authorization": f"Bearer {await db.get('delivery_api_key')}"})
            bal = float(data.get("balance"))
    except Exception as e:
        log.warning("balance check: %s", e)
        return
    if bal < limit and time.time() - _low_balance_alerted > 3600:
        _low_balance_alerted = time.time()
        unit = " TON" if fragment else ""
        await notify_admins(bot, f"🪫 <b>Низкий баланс для выдачи:</b> {bal:g}{unit}")


async def _scheduled_broadcasts(bot: Bot):
    for b in await db.all("SELECT id FROM broadcasts WHERE status='scheduled' AND send_at<=?", int(time.time())):
        asyncio.create_task(run_broadcast(bot, b["id"]))


async def _daily_backup(bot: Bot):
    chat = await db.get("backup_chat_id")
    if not chat:
        return
    last = await db.get_float("last_backup")
    if time.time() - last >= 86400:
        await db.set("last_backup", str(int(time.time())))
        await backup(bot, chat)


async def background(bot: Bot):
    jobs = [("payments", 20, _check_payments), ("retry", 30, _retry_deliveries), ("refund", 60, _auto_refund),
            ("expire", 60, _expire_and_remind), ("broadcasts", 30, _scheduled_broadcasts),
            ("low_balance", 600, _low_balance), ("rate", 1800, lambda b: update_auto_rate()),
            ("backup", 600, _daily_backup)]
    while True:
        for name, every, job in jobs:
            if _due(name, every):
                try:
                    await job(bot)
                except Exception as e:
                    log.exception("job %s: %s", name, e)
        await asyncio.sleep(10)
