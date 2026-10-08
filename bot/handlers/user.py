import html
import re

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import services
from ..db import db
from ..render import base_ctx, money, show, sys_btn

router = Router()
USERNAME = re.compile(r"^(?:@|https?://t\.me/|t\.me/)?([A-Za-z][A-Za-z0-9_]{3,31})$")


class S(StatesGroup):
    amount = State()
    recipient = State()
    promo = State()
    topup = State()
    receipt = State()


async def ctx_for(bot: Bot, user: dict, **extra) -> dict:
    ctx = await base_ctx(bot, user)
    ctx.update(extra)
    return ctx


async def fresh(user: dict) -> dict:
    return await db.user(user["id"])


# ---------- навигация ----------

@router.message(CommandStart())
async def start(m: Message, state: FSMContext, user: dict):
    await state.clear()
    await show(m, "main", await ctx_for(m.bot, user))


@router.callback_query(F.data.startswith("s:"))
async def open_screen(c: CallbackQuery, state: FSMContext, user: dict):
    await state.clear()
    key = c.data[2:]
    if key in FUNCS:  # экран со встроенной логикой
        return await FUNCS[key](c, state, await fresh(user))
    await show(c, key, await ctx_for(c.bot, await fresh(user)))
    await c.answer()


@router.callback_query(F.data.startswith("a:"))
async def alert_button(c: CallbackQuery):
    b = await db.one("SELECT value FROM buttons WHERE id=?", int(c.data[2:]))
    await c.answer((b or {}).get("value", "")[:200] or "…", show_alert=True)


@router.callback_query(F.data.startswith("f:"))
async def func_button(c: CallbackQuery, state: FSMContext, user: dict):
    await state.clear()
    fn = FUNCS.get(c.data[2:])
    if fn:
        await fn(c, state, await fresh(user))
    else:
        await c.answer()


# ---------- встроенные функции ----------

async def f_menu(c, state, user):
    await show(c, "main", await ctx_for(c.bot, user))
    await c.answer()


async def _packages(c, user, gift: int):
    ctx = await ctx_for(c.bot, user)
    rows, row = [], []
    for p in await db.all("SELECT * FROM packages WHERE enabled=1 ORDER BY stars"):
        price = money(p["price"] if p["price"] is not None else await services.price_for(p["stars"]))
        row.append(await sys_btn("package", {**ctx, "stars": p["stars"], "price": price},
                                 callback_data=f"pkg:{p['stars']}:{gift}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([await sys_btn("custom_amount", ctx, callback_data=f"cust:{gift}")])
    await show(c, "buy", ctx, top=rows)
    await c.answer()


async def f_buy(c, state, user):
    await _packages(c, user, 0)


async def f_gift(c, state, user):
    await _packages(c, user, 1)


async def f_buy_custom(c, state, user):
    await state.set_state(S.amount)
    await state.update_data(gift=0)
    await show(c, "ask_amount", await ctx_for(c.bot, user))
    await c.answer()


async def f_profile(c, state, user):
    st = await db.one("SELECT COUNT(*) n, COALESCE(SUM(stars),0) s FROM orders "
                      "WHERE user_id=? AND kind='stars' AND status='done'", user["id"])
    ctx = await ctx_for(c.bot, user, orders_count=st["n"], total_stars=st["s"])
    rows = [[await sys_btn("history", ctx, callback_data="f:history")]]
    if await db.get_bool("pay_crypto") or await db.get_bool("pay_manual"):
        rows.append([await sys_btn("topup", ctx, callback_data="f:topup")])
    await show(c, "profile", ctx, top=rows)
    await c.answer()


async def f_history(c, state, user):
    orders = await db.all("SELECT * FROM orders WHERE user_id=? AND status!='new' ORDER BY id DESC LIMIT 10",
                          user["id"])
    ctx = await ctx_for(c.bot, user)
    icons = {"done": "✅", "canceled": "❌", "pending": "⏳", "review": "🔎", "paid": "🚀", "failed": "⚠️"}
    lines = []
    for o in orders:
        what = f"{o['stars']} ⭐️ → @{html.escape(o['recipient'])}" if o["kind"] == "stars" else "Пополнение"
        lines.append(f"{icons.get(o['status'], '•')} #{o['id']} · {what} · {money(o['amount'])} {ctx['currency']}")
    ctx["history"] = "\n".join(lines) or "Пока пусто."
    await show(c, "history", ctx)
    await c.answer()


async def f_referral(c, state, user):
    n = await db.one("SELECT COUNT(*) n FROM users WHERE ref_id=?", user["id"])
    ctx = await ctx_for(c.bot, user, ref_count=n["n"], ref_earned=money(user["ref_earned"]))
    share = f"https://t.me/share/url?url={ctx['ref_link']}"
    await show(c, "referral", ctx, top=[[await sys_btn("share_ref", ctx, url=share)]])
    await c.answer()


async def f_promo(c, state, user):
    await state.set_state(S.promo)
    await show(c, "promo_ask", await ctx_for(c.bot, user))
    await c.answer()


async def f_topup(c, state, user):
    await state.set_state(S.topup)
    await show(c, "topup_ask", await ctx_for(c.bot, user))
    await c.answer()


FUNCS = {"menu": f_menu, "buy": f_buy, "gift": f_gift, "buy_custom": f_buy_custom, "profile": f_profile,
         "history": f_history, "referral": f_referral, "promo": f_promo, "topup": f_topup}


# ---------- покупка ----------

async def ask_recipient(event, state: FSMContext, user: dict, stars: int, gift: int):
    await state.set_state(S.recipient)
    await state.update_data(stars=stars)
    ctx = await ctx_for(event.bot, user, stars=stars)
    top = []
    if not gift and user["username"]:
        top.append([await sys_btn("to_self", ctx, callback_data=f"self:{stars}")])
    await show(event, "ask_recipient", ctx, top=top)


@router.callback_query(F.data.startswith("pkg:"))
async def pick_package(c: CallbackQuery, state: FSMContext, user: dict):
    _, stars, gift = c.data.split(":")
    await ask_recipient(c, state, user, int(stars), int(gift))
    await c.answer()


@router.callback_query(F.data.startswith("cust:"))
async def custom_amount(c: CallbackQuery, state: FSMContext, user: dict):
    await state.set_state(S.amount)
    await state.update_data(gift=int(c.data[5:]))
    await show(c, "ask_amount", await ctx_for(c.bot, user))
    await c.answer()


@router.message(S.amount, F.text)
async def amount_entered(m: Message, state: FSMContext, user: dict):
    lo, hi = await db.get_int("min_stars"), await db.get_int("max_stars")
    t = m.text.replace(" ", "")
    if not t.isdigit() or not lo <= int(t) <= hi:
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await ask_recipient(m, state, user, int(t), (await state.get_data()).get("gift", 0))


@router.callback_query(F.data.startswith("self:"))
async def to_self(c: CallbackQuery, state: FSMContext, user: dict):
    if not user["username"]:
        return await c.answer("У вас нет username", show_alert=True)
    await state.clear()
    await checkout(c, user, int(c.data[5:]), user["username"])
    await c.answer()


@router.message(S.recipient, F.text)
async def recipient_entered(m: Message, state: FSMContext, user: dict):
    match = USERNAME.match(m.text.strip())
    stars = (await state.get_data()).get("stars")
    if not match or not stars:
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await state.clear()
    await checkout(m, user, stars, match.group(1))


async def pay_buttons(order: dict, ctx: dict, allow_balance: bool):
    oid = order["id"]
    rows = []
    if allow_balance and await db.get_bool("pay_balance"):
        rows.append([await sys_btn("pay_balance", ctx, callback_data=f"pay:balance:{oid}")])
    if await db.get_bool("pay_crypto") and await db.get("cryptobot_token"):
        rows.append([await sys_btn("pay_crypto", ctx, callback_data=f"pay:crypto:{oid}")])
    if await db.get_bool("pay_manual"):
        rows.append([await sys_btn("pay_manual", ctx, callback_data=f"pay:manual:{oid}")])
    rows.append([await sys_btn("cancel", ctx, callback_data=f"oc:{oid}")])
    return rows


async def checkout(event, user: dict, stars: int, recipient: str):
    order = await services.create_order(user["id"], "stars", await services.price_for(stars), stars, recipient)
    ctx = await services.order_ctx(event.bot, order)
    await show(event, "checkout", ctx, top=await pay_buttons(order, ctx, allow_balance=True))


# ---------- пополнение / промокод ----------

@router.message(S.topup, F.text)
async def topup_entered(m: Message, state: FSMContext, user: dict):
    try:
        amount = round(float(m.text.replace(",", ".").replace(" ", "")), 2)
    except ValueError:
        amount = 0
    if amount < await db.get_float("topup_min") or amount > 1_000_000:
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await state.clear()
    order = await services.create_order(user["id"], "topup", amount)
    ctx = await services.order_ctx(m.bot, order)
    await show(m, "topup_checkout", ctx, top=await pay_buttons(order, ctx, allow_balance=False))


@router.message(S.promo, F.text)
async def promo_entered(m: Message, state: FSMContext, user: dict):
    p = await services.promo_valid(m.text.strip(), user["id"])
    await state.clear()
    if not p:
        return await show(m, "promo_bad", await ctx_for(m.bot, user))
    await db.run("UPDATE users SET promo=? WHERE id=?", p["code"], user["id"])
    await show(m, "promo_ok", await ctx_for(m.bot, user, code=html.escape(p["code"]), discount=money(p["discount"])))


# ---------- оплата ----------

async def own_order(c: CallbackQuery, oid: int, user: dict, statuses=("new",)):
    o = await db.order(oid)
    if not o or o["user_id"] != user["id"] or o["status"] not in statuses:
        await c.answer("Заказ уже неактуален", show_alert=True)
        return None
    return o


@router.callback_query(F.data.startswith("pay:"))
async def pay(c: CallbackQuery, state: FSMContext, user: dict):
    _, method, oid = c.data.split(":")
    o = await own_order(c, int(oid), user)
    if not o:
        return
    if method == "balance" and o["kind"] == "stars":
        # сначала атомарно «захватываем» заказ — защита от двойного списания при повторном нажатии
        if not await db.set_status(o["id"], "pending", ("new",)):
            return await c.answer()
        if not await db.take_balance(user["id"], o["amount"]):
            await db.set_status(o["id"], "new")
            await c.answer()
            return await show(c, "no_balance", await ctx_for(c.bot, await fresh(user)), edit=False)
        await db.run("UPDATE orders SET method='balance' WHERE id=?", o["id"])
        await c.answer()
        await c.message.edit_reply_markup(reply_markup=None)
        await services.mark_paid(c.bot, o["id"])
    elif method == "crypto":
        try:
            inv, url = await services.crypto_invoice(o)
        except Exception as e:
            services.log.warning("invoice: %s", e)
            return await c.answer("Оплата временно недоступна, выберите другой способ", show_alert=True)
        await db.run("UPDATE orders SET method='crypto', invoice_id=?, pay_url=?, status='pending' WHERE id=?",
                     inv, url, o["id"])
        ctx = await services.order_ctx(c.bot, o)
        await show(c, "pay_crypto", ctx, top=[
            [await sys_btn("pay_link", ctx, url=url)],
            [await sys_btn("check_payment", ctx, callback_data=f"chk:{o['id']}")],
            [await sys_btn("cancel", ctx, callback_data=f"oc:{o['id']}")]])
        await c.answer()
    elif method == "manual":
        await db.run("UPDATE orders SET method='manual', status='pending' WHERE id=?", o["id"])
        await state.set_state(S.receipt)
        await state.update_data(order_id=o["id"])
        ctx = await services.order_ctx(c.bot, o)
        await show(c, "pay_manual", ctx, top=[[await sys_btn("cancel", ctx, callback_data=f"oc:{o['id']}")]])
        await c.answer()
    else:
        await c.answer()


@router.callback_query(F.data.startswith("chk:"))
async def check_crypto(c: CallbackQuery, user: dict):
    o = await own_order(c, int(c.data[4:]), user, ("pending",))
    if not o:
        return
    try:
        paid = await services.crypto_is_paid(o["invoice_id"])
    except Exception:
        paid = False
    if not paid:
        s = await db.one("SELECT text FROM screens WHERE key='not_paid'")
        return await c.answer(re.sub(r"<[^>]+>", "", (s or {}).get("text", "Не оплачено"))[:200], show_alert=True)
    await c.answer()
    await services.mark_paid(c.bot, o["id"])


@router.callback_query(F.data.startswith("oc:"))
async def user_cancel(c: CallbackQuery, state: FSMContext, user: dict):
    o = await own_order(c, int(c.data[3:]), user, ("new", "pending"))
    if not o:
        return
    await state.clear()
    await services.cancel(c.bot, o["id"], notify_user=False)
    await show(c, "main", await ctx_for(c.bot, await fresh(user)))
    await c.answer("Заказ отменён")


@router.message(S.receipt, F.photo | F.document)
async def receipt(m: Message, state: FSMContext, user: dict):
    oid = (await state.get_data()).get("order_id")
    o = await db.order(oid) if oid else None
    if not o or not await db.set_status(o["id"], "review", ("pending",)):
        await state.clear()
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await state.clear()
    who = f"@{user['username']}" if user["username"] else user["first_name"]
    caption = f"🧾 <b>Чек по заказу</b>\n{services.order_line(o)}\nОт: {html.escape(who or '')} (<code>{user['id']}</code>)"
    kb = services.order_admin_kb(o["id"], paid=False)
    for t in await services.admin_targets():
        try:
            await m.bot.copy_message(t, m.chat.id, m.message_id, caption=caption, reply_markup=kb)
        except Exception as e:
            services.log.warning("receipt to %s: %s", t, e)
    await show(m, "receipt_sent", await services.order_ctx(m.bot, o))


@router.message(S.receipt)
async def receipt_wrong(m: Message, user: dict):
    await show(m, "bad_input", await ctx_for(m.bot, user))


@router.message()
async def fallback(m: Message, state: FSMContext, user: dict):
    await state.clear()
    await show(m, "main", await ctx_for(m.bot, user))
