import html
import re

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as Btn, Message

from .. import services
from ..db import db
from ..render import base_ctx, bot_username, mask, money, screen_plain, send_key, show, sys_btn

router = Router()
USERNAME = re.compile(r"^(?:@|https?://t\.me/|t\.me/)?([A-Za-z][A-Za-z0-9_]{3,31})$")
KINDS = {"s": "stars", "p": "premium"}


class S(StatesGroup):
    amount = State()
    recipient = State()
    promo = State()
    topup = State()
    receipt = State()
    review = State()
    withdraw_amount = State()
    withdraw_details = State()


async def ctx_for(bot: Bot, user: dict, **extra) -> dict:
    ctx = await base_ctx(bot, user)
    ctx.update(extra)
    return ctx


async def fresh(user: dict) -> dict:
    return await db.user(user["id"])


async def alert(c: CallbackQuery, key: str, user: dict):
    await c.answer(await screen_plain(key, await ctx_for(c.bot, user)), show_alert=True)


# ---------- навигация ----------

@router.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext, user: dict):
    await state.clear()
    args = command.args or ""
    # диплинки из inline-режима и Mini App: buy500 / gift500
    match = re.fullmatch(r"(buy|gift)(\d+)", args)
    if match:
        qty = int(match.group(2))
        if await db.get_int("min_stars") <= qty <= await db.get_int("max_stars"):
            return await ask_recipient(m, state, user, "stars", qty, int(match.group(1) == "gift"))
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
async def alert_button(c: CallbackQuery, user: dict):
    b = await db.one("SELECT id, value FROM buttons WHERE id=?", int(c.data[2:]))
    text = (b or {}).get("value", "")
    lang = (await fresh(user)).get("lang")
    if b and lang and lang != (await db.languages())[0]:
        text = await db.tr("button_value", b["id"], lang) or text
    await c.answer(text[:200] or "…", show_alert=True)


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


async def _packages(c, user, kind: str, gift: int):
    ctx = await ctx_for(c.bot, user)
    rows, row = [], []
    for p in await db.all("SELECT * FROM packages WHERE enabled=1 AND kind=? ORDER BY stars", kind):
        price = await services.base_price(kind, p["stars"])
        if price is None:
            continue
        key = "premium_package" if kind == "premium" else "package"
        row.append(await sys_btn(key, {**ctx, "stars": p["stars"], "months": p["stars"], "price": money(price)},
                                 callback_data=f"pkg:{kind[0]}:{p['stars']}:{gift}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if kind == "stars":
        rows.append([await sys_btn("custom_amount", ctx, callback_data=f"cust:{gift}")])
    await show(c, "premium" if kind == "premium" else "buy", ctx, top=rows)
    await c.answer()


async def f_buy(c, state, user):
    await _packages(c, user, "stars", 0)


async def f_gift(c, state, user):
    await _packages(c, user, "stars", 1)


async def f_premium(c, state, user):
    await _packages(c, user, "premium", 0)


async def f_buy_custom(c, state, user):
    await state.set_state(S.amount)
    await state.update_data(gift=0)
    await show(c, "ask_amount", await ctx_for(c.bot, user))
    await c.answer()


async def f_profile(c, state, user):
    st = await db.one("SELECT COUNT(*) n FROM orders WHERE user_id=? AND kind!='topup' AND status='done'", user["id"])
    pct, bought, nxt = await services.user_level(user["id"])
    ctx = await ctx_for(c.bot, user)
    next_line = ""
    if nxt:
        next_line = (f"Next level: {nxt[1]:g}% from {nxt[0]} ⭐️ (left {nxt[0] - bought})" if ctx["_lang"] == "en"
                     else f"Следующий уровень: {nxt[1]:g}% от {nxt[0]} ⭐️ (осталось {nxt[0] - bought})")
    ctx.update(orders_count=st["n"], total_stars=bought, level_discount=f"{pct:g}", next_level=next_line)
    rows = [[await sys_btn("history", ctx, callback_data="f:history")]]
    if await services.enabled_methods():
        rows.append([await sys_btn("topup", ctx, callback_data="f:topup")])
    if len(await db.languages()) > 1:
        rows.append([await sys_btn("change_lang", ctx, callback_data="f:lang")])
    await show(c, "profile", ctx, top=rows)
    await c.answer()


async def f_history(c, state, user):
    orders = await db.all("SELECT * FROM orders WHERE user_id=? AND status!='new' ORDER BY id DESC LIMIT 10",
                          user["id"])
    ctx = await ctx_for(c.bot, user)
    icons = {"done": "✅", "canceled": "❌", "pending": "⏳", "review": "🔎", "paid": "🚀", "failed": "🚀"}
    lines = []
    for o in orders:
        what = services.product_name(o["kind"], o["stars"], ctx["_lang"])
        if o["recipient"]:
            what += f" → @{html.escape(o['recipient'])}"
        lines.append(f"{icons.get(o['status'], '•')} #{o['id']} · {what} · {money(o['amount'])} {ctx['currency']}")
    ctx["history"] = "\n".join(lines) or "—"
    await show(c, "history", ctx)
    await c.answer()


async def f_referral(c, state, user):
    n1 = (await db.one("SELECT COUNT(*) n FROM users WHERE ref_id=?", user["id"]))["n"]
    n2 = (await db.one("SELECT COUNT(*) n FROM users WHERE ref_id IN (SELECT id FROM users WHERE ref_id=?)",
                       user["id"]))["n"]
    ctx = await ctx_for(c.bot, user, ref_count=n1, ref_count2=n2, ref_earned=money(user["ref_earned"]),
                        withdraw_available=money(await services.withdraw_available(user)))
    share = f"https://t.me/share/url?url={ctx['ref_link']}"
    await show(c, "referral", ctx, top=[[await sys_btn("share_ref", ctx, url=share)],
                                        [await sys_btn("withdraw", ctx, callback_data="f:withdraw")]])
    await c.answer()


async def f_withdraw(c, state, user):
    avail = await services.withdraw_available(user)
    ctx = await ctx_for(c.bot, user, withdraw_available=money(avail))
    if avail < await db.get_float("withdraw_min") or avail <= 0:
        await show(c, "withdraw_unavailable", ctx, top=[[await sys_btn("menu", ctx, callback_data="f:referral")]])
        return await c.answer()
    await state.set_state(S.withdraw_amount)
    await show(c, "withdraw_ask", ctx)
    await c.answer()


async def f_promo(c, state, user):
    await state.set_state(S.promo)
    await show(c, "promo_ask", await ctx_for(c.bot, user))
    await c.answer()


async def f_topup(c, state, user):
    await state.set_state(S.topup)
    await show(c, "topup_ask", await ctx_for(c.bot, user))
    await c.answer()


async def f_lang(c, state, user):
    ctx = await ctx_for(c.bot, user)
    names = await db.lang_names()
    rows = [[Btn(text=names.get(code, code), callback_data=f"lang:{code}")] for code in await db.languages()]
    await show(c, "lang", ctx, top=rows)
    await c.answer()


FUNCS = {"menu": f_menu, "buy": f_buy, "gift": f_gift, "premium": f_premium, "buy_custom": f_buy_custom,
         "profile": f_profile, "history": f_history, "referral": f_referral, "withdraw": f_withdraw,
         "promo": f_promo, "topup": f_topup, "lang": f_lang}


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(c: CallbackQuery, user: dict):
    code = c.data[5:]
    if code in await db.languages():
        await db.run("UPDATE users SET lang=? WHERE id=?", code, user["id"])
    await show(c, "main", await ctx_for(c.bot, await fresh(user)))
    await c.answer()


# ---------- покупка ----------

async def ask_recipient(event, state: FSMContext, user: dict, kind: str, qty: int, gift: int):
    await state.set_state(S.recipient)
    await state.update_data(kind=kind, qty=qty)
    ctx = await ctx_for(event.bot, user, stars=qty, months=qty)
    ctx["product"] = services.product_name(kind, qty, ctx["_lang"])
    top = []
    if not gift and user["username"]:
        top.append([await sys_btn("to_self", ctx, callback_data="self")])
    await show(event, "ask_recipient", ctx, top=top)


@router.callback_query(F.data.startswith("pkg:"))
async def pick_package(c: CallbackQuery, state: FSMContext, user: dict):
    _, kind, qty, gift = c.data.split(":")
    await ask_recipient(c, state, user, KINDS.get(kind, "stars"), int(qty), int(gift))
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
    await ask_recipient(m, state, user, "stars", int(t), (await state.get_data()).get("gift", 0))


@router.callback_query(F.data == "self")
async def to_self(c: CallbackQuery, state: FSMContext, user: dict):
    data = await state.get_data()
    if not user["username"]:
        return await alert(c, "alert_no_username", user)
    if not data.get("qty"):
        return await alert(c, "alert_stale", user)
    await state.clear()
    await c.answer()
    await checkout(c, user, data["kind"], data["qty"], user["username"], user["first_name"] or "")


@router.message(S.recipient, F.text)
async def recipient_entered(m: Message, state: FSMContext, user: dict):
    match = USERNAME.match(m.text.strip())
    data = await state.get_data()
    if not match or not data.get("qty"):
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    username = match.group(1)
    exists, name = await services.lookup_recipient(username)
    if not exists:
        return await show(m, "recipient_not_found", await ctx_for(m.bot, user, recipient=html.escape(username)))
    await state.clear()
    await checkout(m, user, data["kind"], data["qty"], username, name)


async def pay_buttons(order: dict, ctx: dict, allow_balance: bool):
    oid = order["id"]
    rows = []
    if allow_balance and await db.get_bool("pay_balance"):
        rows.append([await sys_btn("pay_balance", ctx, callback_data=f"pay:balance:{oid}")])
    for method in await services.enabled_methods():
        rows.append([await sys_btn(f"pay_{method}", ctx, callback_data=f"pay:{method}:{oid}")])
    rows.append([await sys_btn("cancel", ctx, callback_data=f"oc:{oid}")])
    return rows


async def checkout(event, user: dict, kind: str, qty: int, recipient: str, recipient_name: str = ""):
    price = await services.base_price(kind, qty)
    if price is None:
        return await show(event, "bad_input", await ctx_for(event.bot, user))
    if not await services.fraud_check(user, price, recipient):
        return await show(event, "limit_reached", await ctx_for(event.bot, user))
    order = await services.create_order(user, kind, price, qty, recipient, recipient_name)
    await show_checkout(event, order)


async def show_checkout(event, order: dict):
    ctx = await services.order_ctx(event.bot, order)
    key = "topup_checkout" if order["kind"] == "topup" else "checkout"
    await show(event, key, ctx, top=await pay_buttons(order, ctx, allow_balance=order["kind"] != "topup"))


async def show_payment(event, order: dict, state: FSMContext | None = None):
    ctx = await services.order_ctx(event.bot, order)
    oid, method = order["id"], order["method"]
    check = [await sys_btn("check_payment", ctx, callback_data=f"chk:{oid}")]
    cancel = [await sys_btn("cancel", ctx, callback_data=f"oc:{oid}")]
    if method in ("crypto", "yookassa"):
        top = [[await sys_btn("pay_link", ctx, url=order["pay_url"])], check, cancel]
    elif method == "ton":
        top = [[await sys_btn("ton_link", ctx, url=order["pay_url"])],
               [await sys_btn("copy_address", ctx, copy=await db.get("ton_wallet")),
                await sys_btn("copy_comment", ctx, copy=services.ton_comment(oid))], check, cancel]
    else:  # manual
        if state:
            await state.set_state(S.receipt)
            await state.update_data(order_id=oid)
        top = [cancel]
    await show(event, f"pay_{method}", ctx, top=top)


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
    await show_checkout(m, await services.create_order(user, "topup", amount))


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
        await alert(c, "alert_stale", user)
        return None
    return o


@router.callback_query(F.data.startswith("pay:"))
async def pay(c: CallbackQuery, state: FSMContext, user: dict):
    _, method, oid = c.data.split(":")
    o = await own_order(c, int(oid), user)
    if not o:
        return
    if method == "balance" and o["kind"] != "topup":
        # сначала атомарно «захватываем» заказ — защита от двойного списания при повторном нажатии
        if not await db.set_status(o["id"], "pending", ("new",)):
            return await c.answer()
        if not await db.take_balance(user["id"], o["amount"]):
            await db.set_status(o["id"], "new")
            await c.answer()
            return await show(c, "no_balance", await ctx_for(c.bot, await fresh(user)), edit=False)
        await db.run("UPDATE orders SET method='balance' WHERE id=?", o["id"])
        await c.answer()
        try:
            await c.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await services.mark_paid(c.bot, o["id"])
        return
    if method not in await services.enabled_methods():
        return await alert(c, "alert_pay_unavailable", user)
    inv = url = amount = None
    try:
        if method == "crypto":
            inv, url = await services.crypto_invoice(o)
        elif method == "yookassa":
            inv, url = await services.yk_invoice(o, f"https://t.me/{await bot_username(c.bot)}")
        elif method == "ton":
            amount, url = await services.ton_prepare(o)
    except Exception as e:
        services.log.warning("invoice %s: %s", method, e)
        return await alert(c, "alert_pay_unavailable", user)
    if not await db.set_status(o["id"], "pending", ("new",)):
        return await c.answer()
    await db.run("UPDATE orders SET method=?, invoice_id=?, pay_url=?, pay_amount=? WHERE id=?",
                 method, inv, url, amount, o["id"])
    await c.answer()
    await show_payment(c, await db.order(o["id"]), state)


@router.callback_query(F.data.startswith("cont:"))
async def continue_order(c: CallbackQuery, state: FSMContext, user: dict):
    o = await own_order(c, int(c.data[5:]), user, ("new", "pending"))
    if not o:
        return
    await c.answer()
    if o["status"] == "new":
        await show_checkout(c, o)
    else:
        await show_payment(c, o, state)


@router.callback_query(F.data.startswith("chk:"))
async def check_payment(c: CallbackQuery, user: dict):
    o = await own_order(c, int(c.data[4:]), user, ("pending",))
    if not o:
        return
    try:
        paid = await services.is_paid(o)
    except Exception:
        paid = False
    if not paid:
        return await alert(c, "not_paid", user)
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
    await c.answer()


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


# ---------- отзывы ----------

@router.callback_query(F.data.startswith("rv:"))
async def review_rate(c: CallbackQuery, state: FSMContext, user: dict):
    _, oid, rating = c.data.split(":")
    o = await db.order(int(oid))
    if not o or o["user_id"] != user["id"] or o["status"] != "done" or \
            await db.one("SELECT 1 FROM reviews WHERE order_id=?", o["id"]):
        return await alert(c, "alert_stale", user)
    await db.run("INSERT INTO reviews (order_id, user_id, rating, text, created) VALUES (?,?,?, '', strftime('%s'))",
                 o["id"], user["id"], int(rating))
    await state.set_state(S.review)
    await state.update_data(order_id=o["id"])
    ctx = await ctx_for(c.bot, user)
    await show(c, "review_text", ctx, top=[[await sys_btn("review_skip", ctx, callback_data=f"rvs:{o['id']}")]])
    await c.answer()


async def publish_review(bot: Bot, user: dict, oid: int, text: str):
    r = await db.one("SELECT * FROM reviews WHERE order_id=?", oid)
    if not r:
        return
    await db.run("UPDATE reviews SET text=? WHERE id=?", text[:1000], r["id"])
    o = await db.order(oid)
    ctx = await services.order_ctx(bot, o)
    ctx.update(_lang=(await db.languages())[0], rating_stars="⭐️" * r["rating"],
               review_text=html.escape(text[:1000]) or "—",
               name_masked=html.escape(mask(user["username"]) if user["username"] else (user["first_name"] or "")[:1] + "***"))
    ctx["product"] = services.product_name(o["kind"], o["stars"], ctx["_lang"])
    channel = await db.get("reviews_channel")
    if r["rating"] >= 4 and channel:
        try:
            await send_key(bot, channel, "review_post", ctx)
        except Exception as e:
            services.log.warning("review post: %s", e)
    else:
        await services.notify_admins(bot, f"📝 Отзыв {ctx['rating_stars']} по заказу #{oid} от "
                                          f"<code>{user['id']}</code>:\n{ctx['review_text']}")


@router.callback_query(F.data.startswith("rvs:"))
async def review_skip(c: CallbackQuery, state: FSMContext, user: dict):
    await state.clear()
    await publish_review(c.bot, user, int(c.data[4:]), "")
    await show(c, "review_thanks", await ctx_for(c.bot, user))
    await c.answer()


@router.message(S.review, F.text)
async def review_text(m: Message, state: FSMContext, user: dict):
    oid = (await state.get_data()).get("order_id")
    await state.clear()
    if oid:
        await publish_review(m.bot, user, oid, m.text)
    await show(m, "review_thanks", await ctx_for(m.bot, user))


# ---------- вывод реферальных ----------

@router.message(S.withdraw_amount, F.text)
async def withdraw_amount(m: Message, state: FSMContext, user: dict):
    try:
        amount = round(float(m.text.replace(",", ".").replace(" ", "")), 2)
    except ValueError:
        amount = 0
    avail = await services.withdraw_available(await fresh(user))
    if not await db.get_float("withdraw_min") <= amount <= avail or amount <= 0:
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await state.set_state(S.withdraw_details)
    await state.update_data(amount=amount)
    await show(m, "withdraw_details", await ctx_for(m.bot, user))


@router.message(S.withdraw_details, F.text)
async def withdraw_details(m: Message, state: FSMContext, user: dict):
    amount = (await state.get_data()).get("amount", 0)
    await state.clear()
    wid = await services.withdraw_create(m.bot, await fresh(user), amount, m.text.strip()[:200])
    if not wid:
        return await show(m, "bad_input", await ctx_for(m.bot, user))
    await show(m, "withdraw_sent", await ctx_for(m.bot, await fresh(user), wid=wid, amount=money(amount)))


@router.message()
async def fallback(m: Message, state: FSMContext, user: dict):
    await state.clear()
    await show(m, "main", await ctx_for(m.bot, user))
