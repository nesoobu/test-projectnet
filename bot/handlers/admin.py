"""Админ-панель: экраны, тексты, медиа, кнопки, пакеты, настройки, заказы и т.д."""
import asyncio
import html
import re
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Message

from .. import defaults, services
from ..config import ADMIN_IDS
from ..db import db
from ..render import base_ctx, money, show

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

STYLES = ["", "primary", "success", "danger"]
STYLE_NAMES = {"": "обычный", "primary": "синий", "success": "зелёный", "danger": "красный"}
ACTIONS = {"screen": "📄 Открыть экран", "func": "⚙️ Функция бота", "url": "🔗 Ссылка",
           "webapp": "📱 Mini App", "copy": "📋 Копировать текст", "alert": "💬 Всплывающий текст"}
KEY_RE = re.compile(r"^[a-z0-9_]{1,20}$")


class A(StatesGroup):
    input = State()


def kb(*rows) -> Kb:
    return Kb(inline_keyboard=[[Btn(text=t, callback_data=d) for t, d in r] for r in rows if r])


def back(to="ad:menu"):
    return [("◀️ Назад", to)]


async def out(event, text: str, markup: Kb | None = None):
    if isinstance(event, CallbackQuery):
        await event.answer()
        try:
            return await event.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            event = event.message
    return await event.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def ask(event, state: FSMContext, kind: str, prompt: str, cancel_to="ad:menu", **data):
    await state.set_state(A.input)
    await state.set_data({"kind": kind, "back": cancel_to, **data})
    await out(event, prompt, kb([("✖️ Отмена", cancel_to)]))


# ================= меню =================

MENU = kb([("📝 Экраны и тексты", "ad:scr"), ("🔘 Системные кнопки", "ad:sys")],
          [("💎 Пакеты звёзд", "ad:pk"), ("⚙️ Настройки", "ad:set")],
          [("📦 Заказы", "ad:ord"), ("🎟 Промокоды", "ad:pr")],
          [("👤 Пользователи", "ad:usr"), ("📢 Рассылка", "ad:bc")],
          [("📊 Статистика", "ad:stats")])


@router.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Админ-панель</b>", reply_markup=MENU)


@router.callback_query(F.data == "ad:menu")
async def admin_menu(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await out(c, "🛠 <b>Админ-панель</b>", MENU)


# ================= экраны =================

@router.callback_query(F.data == "ad:scr")
async def screens_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    screens = await db.all("SELECT key, title, media_id FROM screens ORDER BY builtin, title")
    rows = [[(f"{'🖼 ' if s['media_id'] else ''}{s['title']}", f"ad:s:{s['key']}")] for s in screens]
    rows = [sum(rows[i:i + 2], []) for i in range(0, len(rows), 2)]
    await out(c, "📝 <b>Экраны</b>\n\nКаждый экран — это текст, медиа и кнопки. "
                 "Плейсхолдеры: <code>{name} {id} {balance} {currency} {rate} {support} {ref_link}</code> и др.",
              kb(*rows, [("➕ Новый экран", "ad:snew")], back()))


async def screen_view(event, key: str):
    s = await db.one("SELECT * FROM screens WHERE key=?", key)
    if not s:
        return await out(event, "Экран не найден", kb(back("ad:scr")))
    n = (await db.one("SELECT COUNT(*) n FROM buttons WHERE screen=?", key))["n"]
    preview = html.escape(s["text"][:1500])
    text = (f"📄 <b>{html.escape(s['title'])}</b> (<code>{key}</code>)\n"
            f"Медиа: {s['media_type'] or 'нет'} · Кнопок: {n}\n\n<pre>{preview}</pre>")
    rows = [[("✏️ Текст", f"ad:st:{key}"), ("🖼 Медиа", f"ad:sm:{key}")],
            [("🗑 Убрать медиа", f"ad:smd:{key}")] if s["media_id"] else None,
            [(f"🔘 Кнопки ({n})", f"ad:sb:{key}"), ("👁 Превью", f"ad:sp:{key}")],
            [("✏️ Название", f"ad:sn:{key}")],
            None if s["builtin"] else [("🗑 Удалить экран", f"ad:sdel:{key}")],
            back("ad:scr")]
    await out(event, text, kb(*rows))


@router.callback_query(F.data.startswith("ad:s:"))
async def screen_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await screen_view(c, c.data[5:])


@router.callback_query(F.data.startswith("ad:st:"))
async def screen_text(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    await ask(c, state, "scr_text", "✏️ Пришлите новый текст экрана.\n\nФорматирование (жирный, ссылки, "
              "спойлеры, премиум-эмодзи) сохранится. Плейсхолдеры вида <code>{balance}</code> подставятся.",
              f"ad:s:{key}", key=key)


@router.callback_query(F.data.startswith("ad:sm:"))
async def screen_media(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    await ask(c, state, "scr_media", "🖼 Пришлите фото, видео, GIF или файл.\n"
              "Если добавить подпись — она станет текстом экрана.", f"ad:s:{key}", key=key)


@router.callback_query(F.data.startswith("ad:smd:"))
async def screen_media_del(c: CallbackQuery):
    key = c.data[7:]
    await db.run("UPDATE screens SET media_type=NULL, media_id=NULL WHERE key=?", key)
    await screen_view(c, key)


@router.callback_query(F.data.startswith("ad:sn:"))
async def screen_rename(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    await ask(c, state, "scr_title", "Новое название экрана (видно только в админке):", f"ad:s:{key}", key=key)


@router.callback_query(F.data.startswith("ad:sp:"))
async def screen_preview(c: CallbackQuery, user: dict):
    ctx = await base_ctx(c.bot, user)
    ctx.update(order_id=123, stars=100, recipient="durov", amount="145", discount_line="", refund_line="",
               card=html.escape(await db.get("card_details")), total_stars=0, orders_count=0, ref_count=0,
               ref_earned="0", history="—", code="PROMO", discount="10")
    await c.answer()
    await show(c, c.data[6:], ctx, edit=False)


@router.callback_query(F.data == "ad:snew")
async def screen_new(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "scr_new", "➕ Пришлите ключ и название через пробел, например:\n"
              "<code>sale Акция недели</code>\n\nКлюч — латиница/цифры/_, до 20 символов. "
              "Потом повесьте экран на кнопку с действием «Открыть экран».", "ad:scr")


@router.callback_query(F.data.startswith("ad:sdel:"))
async def screen_delete(c: CallbackQuery):
    key = c.data[8:]
    await db.run("DELETE FROM screens WHERE key=? AND builtin=0", key)
    await db.run("DELETE FROM buttons WHERE screen=?", key)
    await db.run("UPDATE buttons SET enabled=0 WHERE action='screen' AND value=?", key)
    await c.answer("Удалено. Кнопки, которые вели на экран, выключены.", show_alert=True)
    await out(c, "Экран удалён", kb(back("ad:scr")))


# ================= кнопки =================

def btn_title(b: dict) -> str:
    off = "" if b["enabled"] else "🚫 "
    return f"{off}{b['emoji']} {b['text']}".strip()[:60]


@router.callback_query(F.data.startswith("ad:sb:"))
async def buttons_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    key = c.data[6:]
    bs = await db.all("SELECT * FROM buttons WHERE screen=? ORDER BY row, pos, id", key)
    rows = [[(f"[{b['row']}.{b['pos']}] {btn_title(b)}", f"ad:b:{b['id']}")] for b in bs]
    await out(c, f"🔘 <b>Кнопки экрана</b> <code>{key}</code>\n\n[ряд.позиция] — порядок отображения. "
                 "Встроенные кнопки (пакеты, оплата) выводятся над ними и настраиваются в «Системных кнопках».",
              kb(*rows, [("➕ Добавить кнопку", f"ad:badd:{key}")], back(f"ad:s:{key}")))


@router.callback_query(F.data == "ad:sys")
async def sys_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    bs = await db.all("SELECT * FROM buttons WHERE screen='__sys__' ORDER BY id")
    rows = [[(f"{btn_title(b)}  ·  {b['value']}", f"ad:b:{b['id']}")] for b in bs]
    await out(c, "🔘 <b>Системные кнопки</b>\n\nКнопки, которые бот строит сам. Можно менять текст, эмодзи, "
                 "премиум-эмодзи и цвет. Плейсхолдеры: <code>{stars} {price} {currency} {balance}</code>",
              kb(*rows, back()))


async def button_view(event, bid: int):
    b = await db.one("SELECT * FROM buttons WHERE id=?", bid)
    if not b:
        return await out(event, "Кнопка не найдена", kb(back()))
    sys = b["screen"] == "__sys__"
    act = "" if sys else (f"\nДействие: {ACTIONS.get(b['action'], b['action'])} → "
                          f"<code>{html.escape(b['value'] or '')}</code>"
                          f"\nПозиция: ряд {b['row']}, место {b['pos']}\nВключена: {'да' if b['enabled'] else 'нет'}")
    text = (f"🔘 <b>Кнопка</b>\n\nТекст: <code>{html.escape(b['text'])}</code>\n"
            f"Эмодзи: {b['emoji'] or '—'}\nПремиум-эмодзи: <code>{b['icon_id'] or '—'}</code>\n"
            f"Цвет: {STYLE_NAMES.get(b['style'], b['style'])}{act}")
    rows = [[("✏️ Текст", f"ad:bt:{bid}"), ("😀 Эмодзи", f"ad:be:{bid}")],
            [("✨ Премиум-эмодзи", f"ad:bi:{bid}"), (f"🎨 Цвет: {STYLE_NAMES.get(b['style'])}", f"ad:bs:{bid}")]]
    if not sys:
        rows += [[("⚡️ Действие", f"ad:ba:{bid}"), ("↕️ Позиция", f"ad:bp:{bid}")],
                 [("🚫 Выключить" if b["enabled"] else "✅ Включить", f"ad:bx:{bid}"), ("🗑 Удалить", f"ad:bd:{bid}")]]
    rows.append(back("ad:sys" if sys else f"ad:sb:{b['screen']}"))
    await out(event, text, kb(*rows))


@router.callback_query(F.data.startswith("ad:b:"))
async def button_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await button_view(c, int(c.data[5:]))


@router.callback_query(F.data.startswith("ad:badd:"))
async def button_add(c: CallbackQuery, state: FSMContext):
    key = c.data[8:]
    await ask(c, state, "btn_new", "➕ Пришлите текст новой кнопки (можно с эмодзи в начале).", f"ad:sb:{key}", key=key)


@router.callback_query(F.data.startswith("ad:bt:"))
async def button_text(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    await ask(c, state, "btn_text", "✏️ Новый текст кнопки (до 64 символов):", f"ad:b:{bid}", bid=bid)


@router.callback_query(F.data.startswith("ad:be:"))
async def button_emoji(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    await ask(c, state, "btn_emoji", "😀 Пришлите эмодзи, который будет перед текстом (или <code>-</code> чтобы убрать):",
              f"ad:b:{bid}", bid=bid)


@router.callback_query(F.data.startswith("ad:bi:"))
async def button_icon(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    await ask(c, state, "btn_icon", "✨ Пришлите <b>премиум (кастомный) эмодзи</b> сообщением или его ID "
              "(<code>-</code> чтобы убрать).\n\n⚠️ Работает, если у владельца бота есть Telegram Premium "
              "или бот купил доп. username на Fragment.", f"ad:b:{bid}", bid=bid)


@router.callback_query(F.data.startswith("ad:bs:"))
async def button_style(c: CallbackQuery):
    bid = int(c.data[6:])
    b = await db.one("SELECT style FROM buttons WHERE id=?", bid)
    cur = b["style"] if b["style"] in STYLES else ""
    await db.run("UPDATE buttons SET style=? WHERE id=?", STYLES[(STYLES.index(cur) + 1) % len(STYLES)], bid)
    await button_view(c, bid)


@router.callback_query(F.data.startswith("ad:bx:"))
async def button_toggle(c: CallbackQuery):
    bid = int(c.data[6:])
    await db.run("UPDATE buttons SET enabled=1-enabled WHERE id=?", bid)
    await button_view(c, bid)


@router.callback_query(F.data.startswith("ad:bd:"))
async def button_delete(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    b = await db.one("SELECT screen FROM buttons WHERE id=? AND screen!='__sys__'", bid)
    if b:
        await db.run("DELETE FROM buttons WHERE id=?", bid)
        c.data = f"ad:sb:{b['screen']}"
        return await buttons_list(c, state)
    await c.answer()


@router.callback_query(F.data.startswith("ad:bp:"))
async def button_pos(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    await ask(c, state, "btn_pos", "↕️ Пришлите ряд и позицию через пробел, например <code>2 1</code>.\n"
              "Кнопки с одинаковым рядом встают в одну строку.", f"ad:b:{bid}", bid=bid)


@router.callback_query(F.data.startswith("ad:ba:"))
async def button_action(c: CallbackQuery):
    bid = int(c.data[6:])
    rows = [[(name, f"ad:bat:{bid}:{a}")] for a, name in ACTIONS.items()]
    await out(c, "⚡️ Что делает кнопка?", kb(*rows, back(f"ad:b:{bid}")))


@router.callback_query(F.data.startswith("ad:bat:"))
async def button_action_type(c: CallbackQuery, state: FSMContext):
    _, _, bid, action = c.data.split(":")
    bid = int(bid)
    if action == "screen":
        screens = await db.all("SELECT key, title FROM screens ORDER BY title")
        rows = [[(s["title"], f"ad:bav:{bid}:screen:{s['key']}")] for s in screens]
        return await out(c, "📄 Какой экран открыть?", kb(*rows, back(f"ad:ba:{bid}")))
    if action == "func":
        rows = [[(name, f"ad:bav:{bid}:func:{f}")] for f, name in defaults.FUNCS.items()]
        return await out(c, "⚙️ Какую функцию запускать?", kb(*rows, back(f"ad:ba:{bid}")))
    prompts = {"url": "🔗 Пришлите ссылку (https://... или tg://...):",
               "webapp": "📱 Пришлите https-ссылку на Mini App:",
               "copy": "📋 Пришлите текст, который скопируется по нажатию (до 256 символов):",
               "alert": "💬 Пришлите текст всплывающего окна (до 200 символов):"}
    await ask(c, state, "btn_value", prompts[action], f"ad:b:{bid}", bid=bid, action=action)


@router.callback_query(F.data.startswith("ad:bav:"))
async def button_action_value(c: CallbackQuery):
    _, _, bid, action, value = c.data.split(":", 4)
    await db.run("UPDATE buttons SET action=?, value=? WHERE id=?", action, value, int(bid))
    await button_view(c, int(bid))


# ================= пакеты =================

@router.callback_query(F.data == "ad:pk")
async def packages(c: CallbackQuery, state: FSMContext):
    await state.clear()
    cur = await db.get("currency")
    rows = []
    for p in await db.all("SELECT * FROM packages ORDER BY stars"):
        price = f"{money(p['price'])}{cur}" if p["price"] is not None else f"{money(await services.price_for(p['stars']))}{cur} (по курсу)"
        rows.append([(f"{'' if p['enabled'] else '🚫 '}{p['stars']} ⭐️ — {price}", f"ad:pkv:{p['id']}")])
    await out(c, f"💎 <b>Пакеты</b>\n\nКурс для своего количества: {await db.get('rate')}{cur} за ⭐️",
              kb(*rows, [("➕ Пакет", "ad:pkadd"), ("💱 Курс", "ad:set:rate")], back()))


@router.callback_query(F.data.startswith("ad:pkv:"))
async def package_view(c: CallbackQuery, state: FSMContext):
    await state.clear()
    pid = int(c.data[7:])
    p = await db.one("SELECT * FROM packages WHERE id=?", pid)
    if not p:
        return await packages(c, state)
    await out(c, f"💎 Пакет <b>{p['stars']} ⭐️</b>\nЦена: {money(p['price']) if p['price'] is not None else 'по курсу'}",
              kb([("💵 Цена", f"ad:pkp:{pid}"), ("🚫 Выкл" if p["enabled"] else "✅ Вкл", f"ad:pkx:{pid}")],
                 [("🗑 Удалить", f"ad:pkd:{pid}")], back("ad:pk")))


@router.callback_query(F.data == "ad:pkadd")
async def package_add(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "pkg_new", "➕ Пришлите количество звёзд и цену через пробел: <code>500 690</code>\n"
              "Без цены (<code>500</code>) — цена считается по курсу.", "ad:pk")


@router.callback_query(F.data.startswith("ad:pkp:"))
async def package_price(c: CallbackQuery, state: FSMContext):
    pid = int(c.data[7:])
    await ask(c, state, "pkg_price", "💵 Новая цена пакета (<code>-</code> = по курсу):", f"ad:pkv:{pid}", pid=pid)


@router.callback_query(F.data.startswith("ad:pkx:"))
async def package_toggle(c: CallbackQuery, state: FSMContext):
    await db.run("UPDATE packages SET enabled=1-enabled WHERE id=?", int(c.data[7:]))
    await package_view(c, state)


@router.callback_query(F.data.startswith("ad:pkd:"))
async def package_delete(c: CallbackQuery, state: FSMContext):
    await db.run("DELETE FROM packages WHERE id=?", int(c.data[7:]))
    await packages(c, state)


# ================= настройки =================

@router.callback_query(F.data == "ad:set")
async def settings_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = []
    for k, (_, desc, typ) in defaults.SETTINGS.items():
        v = await db.get(k)
        if typ == "bool":
            shown = "✅" if v == "1" else "❌"
        elif "token" in k or "key" in k:
            shown = "••••" if v else "—"
        else:
            shown = (v or "—")[:18]
        rows.append([(f"{desc[:30]}: {shown}", f"ad:set:{k}")])
    await out(c, "⚙️ <b>Настройки</b>\n\nНажмите, чтобы изменить. Переключатели меняются сразу.", kb(*rows, back()))


@router.callback_query(F.data.startswith("ad:set:"))
async def setting_edit(c: CallbackQuery, state: FSMContext):
    key = c.data[7:]
    if key not in defaults.SETTINGS:
        return await c.answer()
    _, desc, typ = defaults.SETTINGS[key]
    if typ == "bool":
        await db.set(key, "0" if await db.get_bool(key) else "1")
        return await settings_list(c, state)
    cur = await db.get(key)
    if "token" in key or "key" in key:
        cur = "••••" if cur else ""
    await ask(c, state, "set", f"⚙️ <b>{desc}</b>\nТекущее: <code>{html.escape(cur or '—')}</code>\n\n"
              "Пришлите новое значение (<code>-</code> — очистить):", "ad:set", key=key, typ=typ)


# ================= заказы =================

@router.callback_query(F.data == "ad:ord")
async def orders_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    orders = await db.all("SELECT * FROM orders WHERE status IN ('review','paid','failed','pending') "
                          "ORDER BY id DESC LIMIT 30")
    rows = [[(services.order_line(o)[:60], f"ad:o:{o['id']}")] for o in orders]
    await out(c, "📦 <b>Активные заказы</b>\n\n🔎 review — чек на проверке\n🚀 paid — оплачен, ждёт выдачи\n"
                 "⚠️ failed — ошибка автовыдачи\n⏳ pending — ждёт оплату\n\nНайти заказ: <code>/order ID</code>",
              kb(*rows, back()))


async def order_view(event, oid: int):
    o = await db.order(oid)
    if not o:
        return await out(event, "Заказ не найден", kb(back("ad:ord")))
    u = await db.user(o["user_id"])
    text = (f"📦 <b>Заказ #{o['id']}</b>\n{services.order_line(o, await db.get('currency'))}\n\n"
            f"Покупатель: {html.escape('@' + u['username'] if u and u['username'] else str(o['user_id']))} "
            f"(<code>{o['user_id']}</code>)\nСоздан: {time.strftime('%d.%m %H:%M', time.localtime(o['created']))}")
    markup = None
    if o["status"] in ("review", "pending", "paid", "failed"):
        markup = services.order_admin_kb(oid, paid=o["status"] in ("paid", "failed"))
        markup.inline_keyboard.append([Btn(text="◀️ Назад", callback_data="ad:ord")])
    await out(event, text, markup or kb(back("ad:ord")))


@router.callback_query(F.data.startswith("ad:o:"))
async def order_open(c: CallbackQuery):
    await order_view(c, int(c.data[5:]))


@router.message(Command("order"))
async def order_cmd(m: Message):
    arg = (m.text.split(maxsplit=1) + [""])[1].lstrip("#")
    if arg.isdigit():
        await order_view(m, int(arg))


async def _order_action(c: CallbackQuery, ok: bool, msg: str):
    await c.answer(msg if ok else "Статус заказа уже изменился", show_alert=not ok)
    if ok:
        try:
            await c.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


@router.callback_query(F.data.startswith("ad:op:"))
async def order_paid(c: CallbackQuery):
    await _order_action(c, await services.mark_paid(c.bot, int(c.data[6:])), "Оплата подтверждена")


@router.callback_query(F.data.startswith("ad:od:"))
async def order_done(c: CallbackQuery):
    await _order_action(c, await services.complete(c.bot, int(c.data[6:])), "Заказ выполнен")


@router.callback_query(F.data.startswith("ad:or:"))
async def order_retry(c: CallbackQuery):
    oid = int(c.data[6:])
    ok = await db.set_status(oid, "paid", ("failed", "paid"))
    await _order_action(c, ok, "Повторная выдача запущена")
    if ok:
        await services.deliver(c.bot, oid)


@router.callback_query(F.data.startswith("ad:oc:"))
async def order_cancel(c: CallbackQuery):
    await _order_action(c, await services.cancel(c.bot, int(c.data[6:])), "Заказ отменён")


# ================= промокоды =================

@router.callback_query(F.data == "ad:pr")
async def promos(c: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[(f"🗑 {p['code']} · -{money(p['discount'])}% · исп. {p['used']} · ост. "
              f"{'∞' if p['uses_left'] < 0 else p['uses_left']}", f"ad:prd:{p['code']}")]
            for p in await db.all("SELECT * FROM promos ORDER BY code")]
    await out(c, "🎟 <b>Промокоды</b>\n\nНажмите на промокод, чтобы удалить. Каждый пользователь может "
                 "применить промокод один раз.", kb(*rows, [("➕ Промокод", "ad:pradd")], back()))


@router.callback_query(F.data == "ad:pradd")
async def promo_add(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "promo_new", "➕ Пришлите: <code>КОД СКИДКА% [КОЛ-ВО]</code>\n"
              "Например <code>SALE10 10 100</code> — скидка 10% на 100 активаций. Без количества — безлимит.", "ad:pr")


@router.callback_query(F.data.startswith("ad:prd:"))
async def promo_delete(c: CallbackQuery, state: FSMContext):
    await db.run("DELETE FROM promos WHERE code=?", c.data[7:])
    await promos(c, state)


# ================= пользователи =================

@router.callback_query(F.data == "ad:usr")
async def users_find(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "user_find", "👤 Пришлите ID или @username пользователя:")


async def user_view(event, uid: int):
    u = await db.user(uid)
    if not u:
        return await out(event, "Пользователь не найден", kb(back()))
    st = await db.one("SELECT COUNT(*) n, COALESCE(SUM(amount),0) s FROM orders "
                      "WHERE user_id=? AND kind='stars' AND status='done'", uid)
    refs = (await db.one("SELECT COUNT(*) n FROM users WHERE ref_id=?", uid))["n"]
    cur = await db.get("currency")
    text = (f"👤 <b>{html.escape(u['first_name'] or '')}</b> {('@' + u['username']) if u['username'] else ''}\n"
            f"ID: <code>{uid}</code>\nБаланс: {money(u['balance'])}{cur}\n"
            f"Заказов: {st['n']} на {money(st['s'])}{cur}\nРефералов: {refs}, заработал {money(u['ref_earned'])}{cur}\n"
            f"Статус: {'⛔️ забанен' if u['banned'] else 'активен'}")
    await out(event, text, kb([("💰 Баланс", f"ad:ub:{uid}"), ("✅ Разбан" if u["banned"] else "⛔️ Бан", f"ad:uban:{uid}")],
                              back()))


@router.callback_query(F.data.startswith("ad:ub:"))
async def user_balance(c: CallbackQuery, state: FSMContext):
    uid = int(c.data[6:])
    await ask(c, state, "user_bal", "💰 Пришлите <code>+100</code>, <code>-50</code> или точное значение <code>200</code>:",
              f"ad:u:{uid}", uid=uid)


@router.callback_query(F.data.startswith("ad:uban:"))
async def user_ban(c: CallbackQuery):
    uid = int(c.data[8:])
    await db.run("UPDATE users SET banned=1-banned WHERE id=?", uid)
    await user_view(c, uid)


@router.callback_query(F.data.startswith("ad:u:"))
async def user_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await user_view(c, int(c.data[5:]))


# ================= рассылка и статистика =================

@router.callback_query(F.data == "ad:bc")
async def broadcast(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "bc", "📢 Пришлите сообщение для рассылки (текст, фото, видео — что угодно). "
              "Оно будет скопировано всем пользователям как есть, вместе с inline-кнопками.")


@router.callback_query(F.data == "ad:bcgo")
async def broadcast_go(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if "msg_id" not in data:
        return await c.answer()
    await out(c, "📢 Рассылка запущена, по завершении пришлю отчёт.")
    asyncio.create_task(_broadcast(c.bot, c.from_user.id, data["chat_id"], data["msg_id"]))


async def _broadcast(bot: Bot, admin: int, chat_id: int, msg_id: int):
    ok = fail = 0
    for u in await db.all("SELECT id FROM users WHERE banned=0"):
        try:
            await bot.copy_message(u["id"], chat_id, msg_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # ~20 сообщений/сек — в пределах лимитов Telegram
    await bot.send_message(admin, f"📢 Рассылка завершена: ✅ {ok}, ❌ {fail}")


@router.callback_query(F.data == "ad:stats")
async def stats(c: CallbackQuery):
    day = int(time.time()) - 86400
    q = "SELECT COUNT(*) n, COALESCE(SUM(stars),0) s, COALESCE(SUM(amount),0) a FROM orders " \
        "WHERE kind='stars' AND status='done'"
    total, today = await db.one(q), await db.one(q + " AND updated>?", day)
    users = (await db.one("SELECT COUNT(*) n FROM users"))["n"]
    new = (await db.one("SELECT COUNT(*) n FROM users WHERE created>?", day))["n"]
    buyers = (await db.one("SELECT COUNT(DISTINCT user_id) n FROM orders WHERE kind='stars' AND status='done'"))["n"]
    bal = (await db.one("SELECT COALESCE(SUM(balance),0) s FROM users"))["s"]
    active = (await db.one("SELECT COUNT(*) n FROM orders WHERE status IN ('review','paid','failed')"))["n"]
    cur = await db.get("currency")
    conv = f"{buyers / users * 100:.1f}%" if users else "—"
    await out(c, f"📊 <b>Статистика</b>\n\n👥 Пользователей: {users} (+{new} за сутки)\n"
                 f"🛒 Покупателей: {buyers} (конверсия {conv})\n\n"
                 f"<b>За сутки:</b> {today['n']} заказов · {today['s']} ⭐️ · {money(today['a'])}{cur}\n"
                 f"<b>Всего:</b> {total['n']} заказов · {total['s']} ⭐️ · {money(total['a'])}{cur}\n\n"
                 f"💰 На балансах пользователей: {money(bal)}{cur}\n📦 Требуют внимания: {active}",
              kb([("🔄 Обновить", "ad:stats")], back()))


# ================= ввод значений =================

def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


@router.message(A.input)
async def admin_input(m: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind")
    text = (m.text or m.caption or "").strip()
    err = None

    if kind == "scr_text":
        # С форматированием из клиента берём html_text, без него — сырой текст (можно писать HTML-теги руками)
        new = m.html_text if (m.entities or m.caption_entities) else text
        if not new:
            err = "Нужен текст"
        else:
            try:
                await m.answer(new, disable_web_page_preview=True)  # превью + проверка HTML
            except TelegramBadRequest as e:
                err = f"Ошибка разметки: {html.escape(e.message)}"
            else:
                await db.run("UPDATE screens SET text=? WHERE key=?", new, data["key"])
                await state.clear()
                return await screen_view(m, data["key"])

    elif kind == "scr_media":
        media = (("photo", m.photo[-1].file_id) if m.photo else ("video", m.video.file_id) if m.video
                 else ("animation", m.animation.file_id) if m.animation
                 else ("document", m.document.file_id) if m.document else None)
        if not media:
            err = "Пришлите фото, видео, GIF или файл"
        else:
            await db.run("UPDATE screens SET media_type=?, media_id=? WHERE key=?", *media, data["key"])
            if m.caption:
                await db.run("UPDATE screens SET text=? WHERE key=?", m.html_text, data["key"])
            await state.clear()
            return await screen_view(m, data["key"])

    elif kind == "scr_title":
        await db.run("UPDATE screens SET title=? WHERE key=?", text[:40], data["key"])
        await state.clear()
        return await screen_view(m, data["key"])

    elif kind == "scr_new":
        parts = text.split(maxsplit=1)
        key = parts[0].lower() if parts else ""
        if not KEY_RE.match(key) or key == "__sys__":
            err = "Ключ: латиница, цифры, _, до 20 символов"
        elif await db.one("SELECT 1 FROM screens WHERE key=?", key):
            err = "Такой ключ уже есть"
        else:
            title = parts[1][:40] if len(parts) > 1 else key
            await db.run("INSERT INTO screens (key, title, text) VALUES (?, ?, ?)", key, title, f"Экран «{title}»")
            await db.run("INSERT INTO buttons (screen, row, pos, emoji, text, action, value) "
                         "VALUES (?, 9, 0, '◀️', 'Назад', 'screen', 'main')", key)
            await state.clear()
            return await screen_view(m, key)

    elif kind == "btn_new":
        emoji, label = _split_emoji(text)
        if not label:
            err = "Нужен текст"
        else:
            last = await db.one("SELECT COALESCE(MAX(row), -1) r FROM buttons WHERE screen=? AND row<9", data["key"])
            cur = await db.run("INSERT INTO buttons (screen, row, pos, emoji, text, action, value) "
                               "VALUES (?, ?, 0, ?, ?, 'alert', 'Скоро!')", data["key"], last["r"] + 1, emoji, label[:64])
            await state.clear()
            await m.answer("Кнопка создана. Теперь выберите, что она делает 👇")
            return await button_view(m, cur.lastrowid)

    elif kind == "btn_text":
        if not text:
            err = "Нужен текст"
        else:
            await db.run("UPDATE buttons SET text=? WHERE id=?", text[:64], data["bid"])

    elif kind == "btn_emoji":
        await db.run("UPDATE buttons SET emoji=? WHERE id=?", "" if text == "-" else text[:8], data["bid"])

    elif kind == "btn_icon":
        icon = next((e.custom_emoji_id for e in (m.entities or []) if e.type == "custom_emoji"), None)
        if not icon and (text == "-" or text.isdigit()):
            icon = "" if text == "-" else text
        if icon is None:
            err = "Пришлите премиум-эмодзи или его числовой ID"
        else:
            await db.run("UPDATE buttons SET icon_id=? WHERE id=?", icon, data["bid"])

    elif kind == "btn_pos":
        p = text.split()
        if len(p) != 2 or not all(x.isdigit() for x in p):
            err = "Формат: <code>ряд позиция</code>"
        else:
            await db.run("UPDATE buttons SET row=?, pos=? WHERE id=?", int(p[0]), int(p[1]), data["bid"])

    elif kind == "btn_value":
        action = data["action"]
        if action in ("url", "webapp") and not re.match(r"^(https?|tg)://", text):
            err = "Нужна ссылка вида https://..."
        elif action == "webapp" and not text.startswith("https://"):
            err = "Mini App открывается только по https://"
        elif not text:
            err = "Пустое значение"
        else:
            await db.run("UPDATE buttons SET action=?, value=? WHERE id=?", action,
                         text[:200] if action == "alert" else text, data["bid"])

    elif kind == "pkg_new":
        p = text.split()
        stars = int(p[0]) if p and p[0].isdigit() else 0
        price = _num(p[1]) if len(p) > 1 else None
        if stars <= 0 or (len(p) > 1 and (price is None or price <= 0)):
            err = "Формат: <code>500 690</code>"
        else:
            await db.run("INSERT INTO packages (stars, price) VALUES (?, ?)", stars, price)
            await state.clear()
            return await m.answer("✅ Пакет добавлен", reply_markup=kb([("💎 К пакетам", "ad:pk")]))

    elif kind == "pkg_price":
        price = None if text == "-" else _num(text)
        if text != "-" and (price is None or price <= 0):
            err = "Нужно число"
        else:
            await db.run("UPDATE packages SET price=? WHERE id=?", price, data["pid"])
            await state.clear()
            return await m.answer("✅ Цена обновлена", reply_markup=kb([("💎 К пакетам", "ad:pk")]))

    elif kind == "set":
        value = "" if text == "-" else text
        if data["typ"] in ("int", "float") and value and (_num(value) is None or _num(value) < 0):
            err = "Нужно число"
        elif data["key"] == "delivery_mode" and value not in ("manual", "api"):
            err = "Допустимо: manual или api"
        else:
            if data["typ"] in ("int", "float") and value:
                value = value.replace(",", ".")
            await db.set(data["key"], value)
            await state.clear()
            return await m.answer("✅ Сохранено", reply_markup=kb([("⚙️ К настройкам", "ad:set")]))

    elif kind == "promo_new":
        p = text.split()
        disc = _num(p[1]) if len(p) > 1 else None
        uses = int(p[2]) if len(p) > 2 and p[2].isdigit() else -1
        if len(p) < 2 or disc is None or not 0 < disc <= 100:
            err = "Формат: <code>КОД 10 [100]</code>"
        else:
            await db.run("INSERT OR REPLACE INTO promos (code, discount, uses_left, used) VALUES (?, ?, ?, 0)",
                         p[0], disc, uses)
            await state.clear()
            return await m.answer("✅ Промокод создан", reply_markup=kb([("🎟 К промокодам", "ad:pr")]))

    elif kind == "user_find":
        if text.lstrip("-").isdigit():
            u = await db.user(int(text))
        else:
            u = await db.one("SELECT * FROM users WHERE username=? COLLATE NOCASE", text.lstrip("@"))
        if not u:
            err = "Не найден"
        else:
            await state.clear()
            return await user_view(m, u["id"])

    elif kind == "user_bal":
        v = _num(text.lstrip("+"))
        if v is None:
            err = "Нужно число"
        else:
            if text[0] in "+-":
                await db.add_balance(data["uid"], v)
            else:
                await db.run("UPDATE users SET balance=? WHERE id=?", round(v, 2), data["uid"])
            await state.clear()
            return await user_view(m, data["uid"])

    elif kind == "bc":
        await state.update_data(chat_id=m.chat.id, msg_id=m.message_id)
        n = (await db.one("SELECT COUNT(*) n FROM users WHERE banned=0"))["n"]
        return await m.answer(f"Отправить это сообщение {n} пользователям?",
                              reply_markup=kb([("✅ Отправить", "ad:bcgo"), ("✖️ Отмена", "ad:menu")]))

    if err:
        return await m.answer(f"⚠️ {err}", reply_markup=kb([("✖️ Отмена", data.get("back", "ad:menu"))]))
    # по умолчанию — вернуться к редактируемой кнопке
    await state.clear()
    await button_view(m, data["bid"])


def _split_emoji(text: str) -> tuple[str, str]:
    """'⭐️ Купить' -> ('⭐️', 'Купить')."""
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and not any(ch.isalnum() for ch in parts[0]):
        return parts[0], parts[1]
    return "", text
