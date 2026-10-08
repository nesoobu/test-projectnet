"""Заказы, оплата (CryptoBot), выдача звёзд, уведомления."""
import asyncio
import html
import logging
import time

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

from .config import ADMIN_IDS
from .db import db
from .render import base_ctx, money, send_key

log = logging.getLogger(__name__)


# ---------- цены и промокоды ----------

async def price_for(stars: int) -> float:
    pkg = await db.one("SELECT price FROM packages WHERE stars=? AND enabled=1 AND price IS NOT NULL", stars)
    if pkg:
        return round(pkg["price"], 2)
    return round(stars * await db.get_float("rate"), 2)


async def promo_valid(code: str, uid: int) -> dict | None:
    p = await db.one("SELECT * FROM promos WHERE code=? COLLATE NOCASE", code)
    if not p or p["uses_left"] == 0:
        return None
    if await db.one("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", p["code"], uid):
        return None
    return p


async def create_order(uid: int, kind: str, amount: float, stars: int = 0, recipient: str = "") -> dict:
    discount, promo = 0.0, None
    if kind == "stars":
        u = await db.user(uid)
        if u and u["promo"]:
            p = await promo_valid(u["promo"], uid)
            if p:
                promo = p["code"]
                discount = round(amount * p["discount"] / 100, 2)
            else:
                await db.run("UPDATE users SET promo=NULL WHERE id=?", uid)
    now = int(time.time())
    cur = await db.run(
        "INSERT INTO orders (user_id, kind, stars, recipient, amount, discount, promo, status, created, updated)"
        " VALUES (?,?,?,?,?,?,?, 'new', ?, ?)",
        uid, kind, stars, recipient, round(amount - discount, 2), discount, promo, now, now)
    return await db.order(cur.lastrowid)


async def order_ctx(bot: Bot, order: dict) -> dict:
    user = await db.user(order["user_id"])
    ctx = await base_ctx(bot, user)
    ctx.update(order_id=order["id"], stars=order["stars"], recipient=html.escape(order["recipient"] or ""),
               amount=money(order["amount"]), card=html.escape(await db.get("card_details")),
               discount_line=(f"\n🎟 Скидка: <b>-{money(order['discount'])} {ctx['currency']}</b> ({order['promo']})"
                              if order["discount"] else ""),
               refund_line="")
    return ctx


# ---------- CryptoBot ----------

async def _crypto_call(method: str, **params):
    token = await db.get("cryptobot_token")
    host = "testnet-pay.crypt.bot" if await db.get_bool("cryptobot_testnet") else "pay.crypt.bot"
    async with aiohttp.ClientSession() as s:
        async with s.post(f"https://{host}/api/{method}", json=params,
                          headers={"Crypto-Pay-API-Token": token}, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json(content_type=None)
    if not data.get("ok"):
        raise RuntimeError(f"CryptoBot {method}: {data.get('error')}")
    return data["result"]


async def crypto_invoice(order: dict) -> tuple[str, str]:
    res = await _crypto_call(
        "createInvoice", currency_type="fiat", fiat=await db.get("fiat_code"),
        amount=money(order["amount"]), accepted_assets=await db.get("crypto_assets"),
        description=f"Заказ #{order['id']}", payload=str(order["id"]),
        expires_in=await db.get_int("order_ttl_min") * 60)
    return str(res["invoice_id"]), res.get("bot_invoice_url") or res.get("pay_url")


async def crypto_is_paid(invoice_id: str) -> bool:
    res = await _crypto_call("getInvoices", invoice_ids=invoice_id)
    items = res.get("items", [])
    return bool(items) and items[0]["status"] == "paid"


# ---------- уведомления ----------

async def admin_targets() -> list:
    chat = await db.get("log_chat_id")
    return [chat] if chat else list(ADMIN_IDS)


async def notify_admins(bot: Bot, text: str, kb: Kb | None = None, photo: str | None = None):
    for t in await admin_targets():
        try:
            if photo:
                await bot.send_photo(t, photo, caption=text, reply_markup=kb)
            else:
                await bot.send_message(t, text, reply_markup=kb)
        except Exception as e:
            log.warning("notify %s failed: %s", t, e)


def order_admin_kb(oid: int, paid: bool) -> Kb:
    rows = []
    if not paid:
        rows.append([Btn(text="✅ Оплата есть", callback_data=f"ad:op:{oid}")])
    else:
        rows.append([Btn(text="✅ Звёзды выданы", callback_data=f"ad:od:{oid}"),
                     Btn(text="🔁 Повторить API", callback_data=f"ad:or:{oid}")])
    rows.append([Btn(text="❌ Отменить" + (" + возврат" if paid else ""), callback_data=f"ad:oc:{oid}")])
    return Kb(inline_keyboard=rows)


def order_line(o: dict, cur: str = "") -> str:
    who = f"@{o['recipient']}" if o["recipient"] else ""
    what = f"{o['stars']}⭐️ → {who}" if o["kind"] == "stars" else "пополнение"
    return f"#{o['id']} · {what} · {money(o['amount'])}{cur} · {o['method'] or '—'} · {o['status']}"


# ---------- жизненный цикл заказа ----------

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
    if (await db.get("delivery_mode")) == "api" and await db.get("delivery_api_url"):
        ok, err = await _deliver_api(order)
        if ok:
            await complete(bot, oid)
            return
        await db.set_status(oid, "failed")
        await notify_admins(bot, f"⚠️ <b>Ошибка автовыдачи</b>\n{order_line(order)}\n<code>{html.escape(err)}</code>",
                            order_admin_kb(oid, paid=True))
        return
    await notify_admins(bot, f"🆕 <b>Выдайте звёзды</b>\n{order_line(order)}", order_admin_kb(oid, paid=True))


async def _deliver_api(order: dict) -> tuple[bool, str]:
    """Универсальный вызов Fragment-провайдера.
    POST {url} JSON {username, quantity, order_id}, заголовок Authorization: Bearer <key>.
    Адаптируйте под своего провайдера при необходимости."""
    url, key = await db.get("delivery_api_url"), await db.get("delivery_api_key")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"username": order["recipient"], "quantity": order["stars"],
                                         "order_id": order["id"]},
                              headers={"Authorization": f"Bearer {key}"},
                              timeout=aiohttp.ClientTimeout(total=60)) as r:
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
    if user and user["ref_id"]:
        bonus = round(order["amount"] * await db.get_float("ref_percent") / 100, 2)
        if bonus > 0:
            await db.add_balance(user["ref_id"], bonus)
            await db.run("UPDATE users SET ref_earned=ROUND(ref_earned+?, 2) WHERE id=?", bonus, user["ref_id"])
    await send_key(bot, order["user_id"], "order_done", await order_ctx(bot, order))
    await notify_admins(bot, f"✅ Выполнен {order_line(order)}")
    return True


async def cancel(bot: Bot, oid: int, notify_user: bool = True) -> bool:
    order = await db.order(oid)
    if not order or order["status"] in ("done", "canceled"):
        return False
    was_paid = order["status"] in ("paid", "failed")
    if not await db.set_status(oid, "canceled", (order["status"],)):
        return False
    ctx = await order_ctx(bot, order)
    if was_paid and order["kind"] == "stars":
        await db.add_balance(order["user_id"], order["amount"])
        ctx["refund_line"] = f"\n💰 {money(order['amount'])} {ctx['currency']} возвращены на баланс."
    if notify_user:
        try:
            await send_key(bot, order["user_id"], "order_canceled", ctx)
        except Exception:
            pass
    return True


# ---------- фоновые задачи ----------

async def background(bot: Bot):
    while True:
        try:
            for o in await db.all("SELECT * FROM orders WHERE status='pending' AND method='crypto'"):
                try:
                    if await crypto_is_paid(o["invoice_id"]):
                        await mark_paid(bot, o["id"])
                except Exception as e:
                    log.warning("crypto check #%s: %s", o["id"], e)
            ttl = await db.get_int("order_ttl_min") * 60
            for o in await db.all("SELECT id FROM orders WHERE status IN ('new','pending') AND created<?",
                                  int(time.time()) - ttl):
                await cancel(bot, o["id"], notify_user=False)
        except Exception as e:
            log.exception("background: %s", e)
        await asyncio.sleep(20)
