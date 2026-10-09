"""Админ-панель: экраны, тексты (мультиязычные), медиа, кнопки, пакеты, настройки, заказы,
выводы, промокоды, пользователи, рассылки, статистика, админы и журнал."""
import asyncio
import html
import re
import time
from datetime import datetime

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Message

from .. import defaults, services
from ..db import db
from ..render import base_ctx, money, show

router = Router()


def is_admin(_, role: str | None = None) -> bool:
    return bool(role)


router.message.filter(is_admin)
router.callback_query.filter(is_admin)

STYLES = ["", "primary", "success", "danger"]
STYLE_NAMES = {"": "обычный", "primary": "синий", "success": "зелёный", "danger": "красный"}
ACTIONS = {"screen": "📄 Открыть экран", "func": "⚙️ Функция бота", "url": "🔗 Ссылка",
           "webapp": "📱 Mini App", "copy": "📋 Копировать текст", "alert": "💬 Всплывающий текст"}
KEY_RE = re.compile(r"^[a-z0-9_]{1,20}$")
# действия, которые пишутся в журнал
LOGGED = ("ad:op:", "ad:od:", "ad:or:", "ad:oc:", "ad:wdok:", "ad:wdno:", "ad:smd:", "ad:sdel:", "ad:bs:",
          "ad:bx:", "ad:bd:", "ad:bav:", "ad:pkx:", "ad:pkd:", "ad:set:", "ad:prd:", "ad:uban:", "ad:bcn",
          "ad:admd:", "ad:bkp")
ADMIN_LANG: dict[int, str] = {}  # язык, который админ сейчас редактирует


class Perm(BaseMiddleware):
    """Права ролей + журнал действий."""

    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery):
            if data.get("role") == "operator" and not event.data.startswith(defaults.OPERATOR_PREFIXES):
                return await event.answer("⛔️ Нет доступа", show_alert=True)
            if event.data.startswith(LOGGED):
                await db.log_admin(event.from_user.id, event.data)
        return await handler(event, data)


router.callback_query.middleware(Perm())


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


async def edit_lang(uid: int) -> tuple[str, bool]:
    """(язык редактирования, это основной язык?)"""
    langs = await db.languages()
    lang = ADMIN_LANG.get(uid, langs[0])
    if lang not in langs:
        lang = langs[0]
    return lang, lang == langs[0]


async def cycle_lang(uid: int):
    langs = await db.languages()
    cur, _ = await edit_lang(uid)
    ADMIN_LANG[uid] = langs[(langs.index(cur) + 1) % len(langs)]


# ================= меню =================

async def menu_kb(role: str, uid: int) -> Kb:
    if role == "operator":
        return kb([("📦 Заказы", "ad:ord"), ("💸 Выводы", "ad:wl")])
    lang, _ = await edit_lang(uid)
    return kb([("📝 Экраны и тексты", "ad:scr"), ("🔘 Системные кнопки", "ad:sys")],
              [("💎 Пакеты", "ad:pk"), ("⚙️ Настройки", "ad:set")],
              [("📦 Заказы", "ad:ord"), ("💸 Выводы", "ad:wl")],
              [("🎟 Промокоды", "ad:pr"), ("👤 Пользователи", "ad:usr")],
              [("📢 Рассылка", "ad:bc"), ("📊 Статистика", "ad:stats")],
              [("📈 Источники (UTM)", "ad:src"), ("⭐️ Отзывы", "ad:rv")],
              [("👮 Админы", "ad:adm"), ("📜 Журнал", "ad:log")],
              [(f"🌐 Язык редактирования: {lang}", "ad:lng"), ("💾 Бэкап", "ad:bkp")])


@router.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext, role: str):
    await state.clear()
    await m.answer("🛠 <b>Админ-панель</b>", reply_markup=await menu_kb(role, m.from_user.id))


@router.callback_query(F.data == "ad:menu")
async def admin_menu(c: CallbackQuery, state: FSMContext, role: str):
    await state.clear()
    await out(c, "🛠 <b>Админ-панель</b>", await menu_kb(role, c.from_user.id))


@router.callback_query(F.data == "ad:lng")
async def switch_lang(c: CallbackQuery, state: FSMContext, role: str):
    await cycle_lang(c.from_user.id)
    await admin_menu(c, state, role)


# ================= экраны =================

@router.callback_query(F.data == "ad:scr")
async def screens_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    screens = await db.all("SELECT key, title, media_id FROM screens ORDER BY builtin, title")
    rows = [[(f"{'🖼 ' if s['media_id'] else ''}{s['title']}", f"ad:s:{s['key']}")] for s in screens]
    rows = [sum(rows[i:i + 2], []) for i in range(0, len(rows), 2)]
    lang, _ = await edit_lang(c.from_user.id)
    await out(c, f"📝 <b>Экраны</b> (язык: {lang})\n\nКаждый экран — текст, медиа и кнопки. Плейсхолдеры: "
                 "<code>{name} {id} {balance} {currency} {rate} {support} {ref_link} {sold_stars} {done_orders}</code>",
              kb(*rows, [("➕ Новый экран", "ad:snew")], back()))


async def screen_view(event, key: str, uid: int):
    s = await db.one("SELECT * FROM screens WHERE key=?", key)
    if not s:
        return await out(event, "Экран не найден", kb(back("ad:scr")))
    lang, is_main = await edit_lang(uid)
    text, note = s["text"], ""
    if not is_main:
        t = await db.tr("screen", key, lang)
        note = "" if t else " ⚠️ перевода нет, показан основной язык"
        text = t or text
    n = (await db.one("SELECT COUNT(*) n FROM buttons WHERE screen=?", key))["n"]
    body = (f"📄 <b>{html.escape(s['title'])}</b> (<code>{key}</code>)\n"
            f"Язык: {lang}{note}\nМедиа: {s['media_type'] or 'нет'} · Кнопок: {n}\n\n"
            f"<pre>{html.escape(text[:1500])}</pre>")
    rows = [[(f"✏️ Текст ({lang})", f"ad:st:{key}"), ("🖼 Медиа", f"ad:sm:{key}")],
            [("🗑 Убрать медиа", f"ad:smd:{key}")] if s["media_id"] else None,
            [(f"🔘 Кнопки ({n})", f"ad:sb:{key}"), ("👁 Превью", f"ad:sp:{key}")],
            [("✏️ Название", f"ad:sn:{key}"), ("🌐 Сменить язык", f"ad:slng:{key}")],
            None if s["builtin"] else [("🗑 Удалить экран", f"ad:sdel:{key}")],
            back("ad:scr")]
    await out(event, body, kb(*rows))


@router.callback_query(F.data.startswith("ad:s:"))
async def screen_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await screen_view(c, c.data[5:], c.from_user.id)


@router.callback_query(F.data.startswith("ad:slng:"))
async def screen_lang(c: CallbackQuery):
    await cycle_lang(c.from_user.id)
    await screen_view(c, c.data[8:], c.from_user.id)


@router.callback_query(F.data.startswith("ad:st:"))
async def screen_text(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    lang, _ = await edit_lang(c.from_user.id)
    await ask(c, state, "scr_text", f"✏️ Пришлите новый текст экрана (язык: <b>{lang}</b>).\n\n"
              "Форматирование (жирный, ссылки, спойлеры, премиум-эмодзи) сохранится. Можно писать HTML вручную. "
              "Плейсхолдеры вида <code>{balance}</code> подставятся.", f"ad:s:{key}", key=key, lang=lang)


@router.callback_query(F.data.startswith("ad:sm:"))
async def screen_media(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    await ask(c, state, "scr_media", "🖼 Пришлите фото, видео, GIF или файл.\n"
              "Если добавить подпись — она станет текстом экрана.", f"ad:s:{key}", key=key)


@router.callback_query(F.data.startswith("ad:smd:"))
async def screen_media_del(c: CallbackQuery):
    key = c.data[7:]
    await db.run("UPDATE screens SET media_type=NULL, media_id=NULL WHERE key=?", key)
    await screen_view(c, key, c.from_user.id)


@router.callback_query(F.data.startswith("ad:sn:"))
async def screen_rename(c: CallbackQuery, state: FSMContext):
    key = c.data[6:]
    await ask(c, state, "scr_title", "Новое название экрана (видно только в админке):", f"ad:s:{key}", key=key)


def sample_ctx(ctx: dict) -> dict:
    ctx.update(order_id=123, stars=100, months=3, recipient="durov", recipient_display="Pavel Durov (@durov)",
               recipient_masked="@du***v", product="100 ⭐️", amount="145", discount_line="", refund_line="",
               card="0000 0000 0000 0000", total_stars=0, orders_count=0, ref_count=0, ref_count2=0,
               ref_earned="0", withdraw_available="0", history="—", code="PROMO", discount="10",
               level_discount="0", next_level="", ton_amount="1.234", ton_wallet="UQ...", ton_comment="order-123",
               wid=1, rating_stars="⭐️⭐️⭐️⭐️⭐️", review_text="Всё супер!", name_masked="@us***r")
    return ctx


@router.callback_query(F.data.startswith("ad:sp:"))
async def screen_preview(c: CallbackQuery, user: dict):
    ctx = sample_ctx(await base_ctx(c.bot, user))
    ctx["_lang"], _ = await edit_lang(c.from_user.id)
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
    await db.run("DELETE FROM i18n WHERE kind='screen' AND ref=?", key)
    await db.run("UPDATE buttons SET enabled=0 WHERE action='screen' AND value=?", key)
    await out(c, "Экран удалён. Кнопки, которые вели на него, выключены.", kb(back("ad:scr")))


# ================= кнопки =================

def btn_title(b: dict) -> str:
    off = "" if b["enabled"] else "🚫 "
    return f"{off}{b['emoji']} {b['text']}".strip()[:60]


async def buttons_list(c: CallbackQuery, key: str):
    bs = await db.all("SELECT * FROM buttons WHERE screen=? ORDER BY row, pos, id", key)
    rows = [[(f"[{b['row']}.{b['pos']}] {btn_title(b)}", f"ad:b:{b['id']}")] for b in bs]
    await out(c, f"🔘 <b>Кнопки экрана</b> <code>{key}</code>\n\n[ряд.позиция] — порядок отображения. "
                 "Встроенные кнопки (пакеты, оплата) выводятся над ними и настраиваются в «Системных кнопках».",
              kb(*rows, [("➕ Добавить кнопку", f"ad:badd:{key}")], back(f"ad:s:{key}")))


@router.callback_query(F.data.startswith("ad:sb:"))
async def buttons_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await buttons_list(c, c.data[6:])


@router.callback_query(F.data == "ad:sys")
async def sys_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    bs = await db.all("SELECT * FROM buttons WHERE screen='__sys__' ORDER BY id")
    rows = [[(f"{btn_title(b)}  ·  {b['value']}", f"ad:b:{b['id']}")] for b in bs]
    await out(c, "🔘 <b>Системные кнопки</b>\n\nКнопки, которые бот строит сам. Можно менять текст (для каждого "
                 "языка), эмодзи, премиум-эмодзи и цвет. Плейсхолдеры: <code>{stars} {months} {price} {currency} {balance}</code>",
              kb(*rows, back()))


async def button_view(event, bid: int, uid: int):
    b = await db.one("SELECT * FROM buttons WHERE id=?", bid)
    if not b:
        return await out(event, "Кнопка не найдена", kb(back()))
    lang, is_main = await edit_lang(uid)
    text = b["text"] if is_main else (await db.tr("button", bid, lang) or f"{b['text']} ⚠️ нет перевода")
    sys = b["screen"] == "__sys__"
    act = "" if sys else (f"\nДействие: {ACTIONS.get(b['action'], b['action'])} → "
                          f"<code>{html.escape(b['value'] or '')}</code>"
                          f"\nПозиция: ряд {b['row']}, место {b['pos']}\nВключена: {'да' if b['enabled'] else 'нет'}")
    body = (f"🔘 <b>Кнопка</b>\n\nТекст ({lang}): <code>{html.escape(text)}</code>\n"
            f"Эмодзи: {b['emoji'] or '—'}\nПремиум-эмодзи: <code>{b['icon_id'] or '—'}</code>\n"
            f"Цвет: {STYLE_NAMES.get(b['style'], b['style'])}{act}")
    rows = [[(f"✏️ Текст ({lang})", f"ad:bt:{bid}"), ("😀 Эмодзи", f"ad:be:{bid}")],
            [("✨ Премиум-эмодзи", f"ad:bi:{bid}"), (f"🎨 Цвет: {STYLE_NAMES.get(b['style'])}", f"ad:bs:{bid}")]]
    if not sys:
        rows += [[("⚡️ Действие", f"ad:ba:{bid}"), ("↕️ Позиция", f"ad:bp:{bid}")],
                 [("🚫 Выключить" if b["enabled"] else "✅ Включить", f"ad:bx:{bid}"), ("🗑 Удалить", f"ad:bd:{bid}")]]
        if b["action"] == "alert" and not is_main:
            rows.append([(f"💬 Текст окна ({lang})", f"ad:bav2:{bid}")])
    rows.append(back("ad:sys" if sys else f"ad:sb:{b['screen']}"))
    await out(event, body, kb(*rows))


@router.callback_query(F.data.startswith("ad:b:"))
async def button_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await button_view(c, int(c.data[5:]), c.from_user.id)


@router.callback_query(F.data.startswith("ad:badd:"))
async def button_add(c: CallbackQuery, state: FSMContext):
    key = c.data[8:]
    await ask(c, state, "btn_new", "➕ Пришлите текст новой кнопки (можно с эмодзи в начале).", f"ad:sb:{key}", key=key)


@router.callback_query(F.data.startswith("ad:bt:"))
async def button_text(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    lang, _ = await edit_lang(c.from_user.id)
    await ask(c, state, "btn_text", f"✏️ Новый текст кнопки (язык: {lang}, до 64 символов):",
              f"ad:b:{bid}", bid=bid, lang=lang)


@router.callback_query(F.data.startswith("ad:bav2:"))
async def button_alert_tr(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[8:])
    lang, _ = await edit_lang(c.from_user.id)
    await ask(c, state, "btn_alert_tr", f"💬 Текст всплывающего окна на языке {lang}:", f"ad:b:{bid}", bid=bid, lang=lang)


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
    await button_view(c, bid, c.from_user.id)


@router.callback_query(F.data.startswith("ad:bx:"))
async def button_toggle(c: CallbackQuery):
    bid = int(c.data[6:])
    await db.run("UPDATE buttons SET enabled=1-enabled WHERE id=?", bid)
    await button_view(c, bid, c.from_user.id)


@router.callback_query(F.data.startswith("ad:bd:"))
async def button_delete(c: CallbackQuery):
    bid = int(c.data[6:])
    b = await db.one("SELECT screen FROM buttons WHERE id=? AND screen!='__sys__'", bid)
    if not b:
        return await c.answer()
    await db.run("DELETE FROM buttons WHERE id=?", bid)
    await db.run("DELETE FROM i18n WHERE kind IN ('button','button_value') AND ref=?", str(bid))
    await buttons_list(c, b["screen"])


@router.callback_query(F.data.startswith("ad:bp:"))
async def button_pos(c: CallbackQuery, state: FSMContext):
    bid = int(c.data[6:])
    await ask(c, state, "btn_pos", "↕️ Пришлите ряд и позицию через пробел, например <code>2 1</code>.\n"
              "Кнопки с одинаковым рядом встают в одну строку.", f"ad:b:{bid}", bid=bid)


@router.callback_query(F.data.startswith("ad:ba:"))
async def button_action(c: CallbackQuery):
    bid = int(c.data[6:])
    rows = [[(name, f"ad:bat:{bid}:{a}")] for a, name in ACTIONS.items()]
    await out(c, "⚡️ Что делает кнопка?\n\nВ ссылках можно использовать плейсхолдеры, например "
                 "<code>https://t.me/{bot_username}</code> или <code>{webapp_link}</code>.",
              kb(*rows, back(f"ad:b:{bid}")))


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
               "webapp": "📱 Пришлите https-ссылку на Mini App (или <code>{webapp_link}</code> — встроенная витрина):",
               "copy": "📋 Пришлите текст, который скопируется по нажатию (до 256 символов):",
               "alert": "💬 Пришлите текст всплывающего окна (до 200 символов):"}
    await ask(c, state, "btn_value", prompts[action], f"ad:b:{bid}", bid=bid, action=action)


@router.callback_query(F.data.startswith("ad:bav:"))
async def button_action_value(c: CallbackQuery):
    _, _, bid, action, value = c.data.split(":", 4)
    await db.run("UPDATE buttons SET action=?, value=? WHERE id=?", action, value, int(bid))
    await button_view(c, int(bid), c.from_user.id)


# ================= пакеты =================

@router.callback_query(F.data == "ad:pk")
async def packages(c: CallbackQuery, state: FSMContext):
    await state.clear()
    cur = await db.get("currency")
    rate = await db.get_float("rate")
    rows = []
    for p in await db.all("SELECT * FROM packages ORDER BY kind DESC, stars"):
        price = p["price"] if p["price"] is not None else p["stars"] * rate
        auto = " (по курсу)" if p["price"] is None else ""
        name = f"👑 {p['stars']} мес." if p["kind"] == "premium" else f"⭐️ {p['stars']}"
        rows.append([(f"{'' if p['enabled'] else '🚫 '}{name} — {money(price)}{cur}{auto}", f"ad:pkv:{p['id']}")])
    rate_note = " (автокурс)" if await db.get_bool("auto_rate") else ""
    await out(c, f"💎 <b>Пакеты</b>\n\nКурс: {money(rate)}{cur} за ⭐️{rate_note}",
              kb(*rows, [("➕ Пакет", "ad:pkadd"), ("💱 Курс", "ad:set:rate")], back()))


async def package_view(c: CallbackQuery, pid: int):
    p = await db.one("SELECT * FROM packages WHERE id=?", pid)
    if not p:
        return await out(c, "Пакет удалён", kb(back("ad:pk")))
    name = f"Premium {p['stars']} мес." if p["kind"] == "premium" else f"{p['stars']} ⭐️"
    await out(c, f"💎 Пакет <b>{name}</b>\nЦена: {money(p['price']) if p['price'] is not None else 'по курсу'}",
              kb([("💵 Цена", f"ad:pkp:{pid}"), ("🚫 Выкл" if p["enabled"] else "✅ Вкл", f"ad:pkx:{pid}")],
                 [("🗑 Удалить", f"ad:pkd:{pid}")], back("ad:pk")))


@router.callback_query(F.data.startswith("ad:pkv:"))
async def package_open(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await package_view(c, int(c.data[7:]))


@router.callback_query(F.data == "ad:pkadd")
async def package_add(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "pkg_new", "➕ Звёзды: <code>500 690</code> (без цены — по курсу)\n"
              "Premium: <code>p 3 1290</code> (месяцев и цена)", "ad:pk")


@router.callback_query(F.data.startswith("ad:pkp:"))
async def package_price(c: CallbackQuery, state: FSMContext):
    pid = int(c.data[7:])
    await ask(c, state, "pkg_price", "💵 Новая цена пакета (<code>-</code> = по курсу, только для звёзд):",
              f"ad:pkv:{pid}", pid=pid)


@router.callback_query(F.data.startswith("ad:pkx:"))
async def package_toggle(c: CallbackQuery):
    pid = int(c.data[7:])
    await db.run("UPDATE packages SET enabled=1-enabled WHERE id=?", pid)
    await package_view(c, pid)


@router.callback_query(F.data.startswith("ad:pkd:"))
async def package_delete(c: CallbackQuery, state: FSMContext):
    await db.run("DELETE FROM packages WHERE id=?", int(c.data[7:]))
    await packages(c, state)


# ================= настройки =================

@router.callback_query(F.data == "ad:set")
async def settings_groups(c: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[(name, f"ad:sg:{g}")] for g, name in defaults.SETTING_GROUPS.items()]
    await out(c, "⚙️ <b>Настройки</b>", kb(*rows, back()))


async def settings_list(c: CallbackQuery, group: str):
    rows = []
    for k, (_, desc, typ, g) in defaults.SETTINGS.items():
        if g != group:
            continue
        v = await db.get(k)
        if typ == "bool":
            shown = "✅" if v == "1" else "❌"
        elif any(x in k for x in ("token", "secret", "_key")):
            shown = "••••" if v else "—"
        else:
            shown = (v or "—")[:16]
        rows.append([(f"{desc[:34]}: {shown}", f"ad:set:{k}")])
    await out(c, f"⚙️ <b>{defaults.SETTING_GROUPS[group]}</b>\n\nНажмите, чтобы изменить. Переключатели меняются сразу.",
              kb(*rows, back("ad:set")))


@router.callback_query(F.data.startswith("ad:sg:"))
async def settings_group(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await settings_list(c, c.data[6:])


@router.callback_query(F.data.startswith("ad:set:"))
async def setting_edit(c: CallbackQuery, state: FSMContext):
    key = c.data[7:]
    if key not in defaults.SETTINGS:
        return await c.answer()
    _, desc, typ, group = defaults.SETTINGS[key]
    if typ == "bool":
        await db.set(key, "0" if await db.get_bool(key) else "1")
        if key == "auto_rate":
            try:
                await services.update_auto_rate()
            except Exception as e:
                await c.answer(f"Не удалось получить курс: {e}"[:200], show_alert=True)
        return await settings_list(c, group)
    cur = await db.get(key)
    if any(x in key for x in ("token", "secret", "_key")):
        cur = "••••" if cur else ""
    await ask(c, state, "set", f"⚙️ <b>{desc}</b>\nТекущее: <code>{html.escape(cur or '—')}</code>\n\n"
              "Пришлите новое значение (<code>-</code> — очистить):", f"ad:sg:{group}", key=key, typ=typ)


# ================= заказы =================

@router.callback_query(F.data == "ad:ord")
async def orders_list(c: CallbackQuery, state: FSMContext):
    await state.clear()
    orders = await db.all("SELECT * FROM orders WHERE status IN ('review','paid','failed','pending') "
                          "ORDER BY id DESC LIMIT 30")
    rows = [[(services.order_line(o)[:60], f"ad:o:{o['id']}")] for o in orders]
    await out(c, "📦 <b>Активные заказы</b>\n\n🔎 review — чек на проверке\n🚀 paid — оплачен, ждёт выдачи\n"
                 "⚠️ failed — ошибка автовыдачи (идут повторы)\n⏳ pending — ждёт оплату\n\n"
                 "Найти заказ: <code>/order ID</code>", kb(*rows, back()))


async def order_view(event, oid: int):
    o = await db.order(oid)
    if not o:
        return await out(event, "Заказ не найден", kb(back("ad:ord")))
    u = await db.user(o["user_id"])
    text = (f"📦 <b>Заказ #{o['id']}</b>\n{services.order_line(o, await db.get('currency'))}\n\n"
            f"Покупатель: {html.escape('@' + u['username'] if u and u['username'] else str(o['user_id']))} "
            f"(<code>{o['user_id']}</code>)\nПолучатель: {html.escape(o['recipient_name'] or '—')}\n"
            f"Скидка: {money(o['discount'])} {html.escape(o['promo'] or '')}\nПопыток выдачи: {o['attempts']}\n"
            f"Создан: {time.strftime('%d.%m %H:%M', time.localtime(o['created']))}")
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


async def _done(c: CallbackQuery, ok: bool, msg: str):
    await c.answer(msg if ok else "Статус уже изменился", show_alert=not ok)
    if ok:
        try:
            await c.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


@router.callback_query(F.data.startswith("ad:op:"))
async def order_paid(c: CallbackQuery):
    await _done(c, await services.mark_paid(c.bot, int(c.data[6:])), "Оплата подтверждена")


@router.callback_query(F.data.startswith("ad:od:"))
async def order_done(c: CallbackQuery):
    await _done(c, await services.complete(c.bot, int(c.data[6:])), "Заказ выполнен")


@router.callback_query(F.data.startswith("ad:or:"))
async def order_retry(c: CallbackQuery):
    oid = int(c.data[6:])
    ok = await db.set_status(oid, "paid", ("failed", "paid"))
    if ok:
        await db.run("UPDATE orders SET attempts=0 WHERE id=?", oid)
    await _done(c, ok, "Повторная выдача запущена")
    if ok:
        await services.deliver(c.bot, oid)


@router.callback_query(F.data.startswith("ad:oc:"))
async def order_cancel(c: CallbackQuery):
    await _done(c, await services.cancel(c.bot, int(c.data[6:])), "Заказ отменён")


# ================= выводы =================

@router.callback_query(F.data == "ad:wl")
async def withdrawals(c: CallbackQuery):
    ws = await db.all("SELECT * FROM withdrawals WHERE status='new' ORDER BY id")
    cur = await db.get("currency")
    text = "💸 <b>Заявки на вывод</b>\n\n" + ("\n\n".join(
        f"#{w['id']} · <code>{w['user_id']}</code> · {money(w['amount'])}{cur}\n<code>{html.escape(w['details'])}</code>"
        for w in ws) or "Нет новых заявок")
    rows = [[(f"✅ #{w['id']}", f"ad:wdok:{w['id']}"), (f"❌ #{w['id']}", f"ad:wdno:{w['id']}")] for w in ws]
    await out(c, text, kb(*rows, back()))


@router.callback_query(F.data.startswith("ad:wdok:") | F.data.startswith("ad:wdno:"))
async def withdraw_decide(c: CallbackQuery):
    ok = c.data.startswith("ad:wdok:")
    await _done(c, await services.withdraw_finish(c.bot, int(c.data[8:]), ok), "Выплачено" if ok else "Отклонено")


# ================= промокоды =================

@router.callback_query(F.data == "ad:pr")
async def promos(c: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[(f"🗑 {p['code']} · -{money(p['discount'])}% · исп. {p['used']} · ост. "
              f"{'∞' if p['uses_left'] < 0 else p['uses_left']}", f"ad:prd:{p['code']}")]
            for p in await db.all("SELECT * FROM promos ORDER BY code")]
    await out(c, "🎟 <b>Промокоды</b>\n\nНажмите на промокод, чтобы удалить. Каждый пользователь может "
                 "применить промокод один раз. Скидка суммируется со скидкой уровня (макс. 90%).",
              kb(*rows, [("➕ Промокод", "ad:pradd")], back()))


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
                      "WHERE user_id=? AND kind!='topup' AND status='done'", uid)
    refs = (await db.one("SELECT COUNT(*) n FROM users WHERE ref_id=?", uid))["n"]
    cur = await db.get("currency")
    text = (f"👤 <b>{html.escape(u['first_name'] or '')}</b> {('@' + u['username']) if u['username'] else ''}\n"
            f"ID: <code>{uid}</code> · язык: {u['lang'] or '—'} · источник: {html.escape(u['source'] or '—')}\n"
            f"Баланс: {money(u['balance'])}{cur}\nЗаказов: {st['n']} на {money(st['s'])}{cur}\n"
            f"Рефералов: {refs}, заработал {money(u['ref_earned'])}{cur}, вывел {money(u['withdrawn'])}{cur}\n"
            f"Регистрация: {time.strftime('%d.%m.%Y', time.localtime(u['created']))}\n"
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


# ================= рассылка =================

@router.callback_query(F.data == "ad:bc")
async def broadcast(c: CallbackQuery, state: FSMContext):
    scheduled = await db.all("SELECT * FROM broadcasts WHERE status='scheduled' ORDER BY send_at")
    rows = [[(f"🗑 #{b['id']} {services.SEGMENTS.get(b['segment'], b['segment'])} · "
              f"{datetime.fromtimestamp(b['send_at']).strftime('%d.%m %H:%M')}", f"ad:bcd:{b['id']}")] for b in scheduled]
    await state.set_state(A.input)
    await state.set_data({"kind": "bc", "back": "ad:menu"})
    await out(c, "📢 <b>Рассылка</b>\n\nПришлите сообщение (текст, фото, видео — что угодно, с inline-кнопками). "
                 "Потом выберете сегмент и время." + ("\n\nЗапланированные (нажмите, чтобы отменить):" if rows else ""),
              kb(*rows, [("✖️ Отмена", "ad:menu")]))


@router.callback_query(F.data.startswith("ad:bcd:"))
async def broadcast_delete(c: CallbackQuery, state: FSMContext):
    await db.run("DELETE FROM broadcasts WHERE id=? AND status='scheduled'", int(c.data[7:]))
    await broadcast(c, state)


@router.callback_query(F.data.startswith("ad:bcs:"))
async def broadcast_segment(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "msg_id" not in data:
        return await c.answer()
    seg = c.data[7:]
    await state.update_data(segment=seg)
    n = await services.segment_count(seg)
    await out(c, f"Сегмент: <b>{services.SEGMENTS.get(seg, seg)}</b> — {n} получателей.\n\nКогда отправить?",
              kb([("🚀 Сейчас", "ad:bcn"), ("🕒 Запланировать", "ad:bct")], [("✖️ Отмена", "ad:menu")]))


async def _schedule(admin_id: int, data: dict, send_at: int) -> int:
    cur = await db.run("INSERT INTO broadcasts (chat_id, msg_id, segment, send_at, status, admin_id) "
                       "VALUES (?, ?, ?, ?, 'scheduled', ?)",
                       data["chat_id"], data["msg_id"], data["segment"], send_at, admin_id)
    return cur.lastrowid


@router.callback_query(F.data == "ad:bcn")
async def broadcast_now(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if "segment" not in data:
        return await c.answer()
    bid = await _schedule(c.from_user.id, data, int(time.time()))
    asyncio.create_task(services.run_broadcast(c.bot, bid))
    await out(c, f"📢 Рассылка #{bid} запущена, по завершении пришлю отчёт.", kb(back()))


@router.callback_query(F.data == "ad:bct")
async def broadcast_time(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "segment" not in data:
        return await c.answer()
    await state.set_state(A.input)
    await state.update_data(kind="bc_time")
    await out(c, f"🕒 Пришлите дату и время: <code>ДД.ММ ЧЧ:ММ</code> (время сервера, сейчас "
                 f"{datetime.now().strftime('%d.%m %H:%M')})", kb([("✖️ Отмена", "ad:menu")]))


# ================= статистика, источники, отзывы =================

@router.callback_query(F.data == "ad:stats")
async def stats(c: CallbackQuery):
    day = int(time.time()) - 86400
    q = "SELECT COUNT(*) n, COALESCE(SUM(CASE WHEN kind='stars' THEN stars ELSE 0 END),0) s, " \
        "COALESCE(SUM(amount),0) a FROM orders WHERE kind!='topup' AND status='done'"
    total, today = await db.one(q), await db.one(q + " AND updated>?", day)
    users = (await db.one("SELECT COUNT(*) n FROM users"))["n"]
    new = (await db.one("SELECT COUNT(*) n FROM users WHERE created>?", day))["n"]
    dau = (await db.one("SELECT COUNT(*) n FROM users WHERE last_seen>?", day))["n"]
    buyers = (await db.one("SELECT COUNT(DISTINCT user_id) n FROM orders WHERE kind!='topup' AND status='done'"))["n"]
    bal = (await db.one("SELECT COALESCE(SUM(balance),0) s FROM users"))["s"]
    active = (await db.one("SELECT COUNT(*) n FROM orders WHERE status IN ('review','paid','failed')"))["n"]
    wd = (await db.one("SELECT COUNT(*) n FROM withdrawals WHERE status='new'"))["n"]
    created = (await db.one("SELECT COUNT(*) n FROM orders WHERE kind!='topup' AND created>?", day))["n"]
    cur = await db.get("currency")
    conv = f"{buyers / users * 100:.1f}%" if users else "—"
    await out(c, f"📊 <b>Статистика</b>\n\n👥 Пользователей: {users} (+{new} за сутки, активных {dau})\n"
                 f"🛒 Покупателей: {buyers} (конверсия {conv})\n\n"
                 f"<b>За сутки:</b> {today['n']} выполнено, {created} создано · {today['s']} ⭐️ · {money(today['a'])}{cur}\n"
                 f"<b>Всего:</b> {total['n']} заказов · {total['s']} ⭐️ · {money(total['a'])}{cur}\n\n"
                 f"💰 На балансах: {money(bal)}{cur}\n📦 Требуют внимания: {active}\n💸 Заявок на вывод: {wd}",
              kb([("🔄 Обновить", "ad:stats")], back()))


@router.callback_query(F.data == "ad:src")
async def sources(c: CallbackQuery):
    rows = await db.all(
        "SELECT COALESCE(u.source, '—') src, COUNT(DISTINCT u.id) users, "
        "COUNT(DISTINCT CASE WHEN o.status='done' THEN u.id END) buyers, "
        "COALESCE(SUM(CASE WHEN o.status='done' THEN o.amount END), 0) revenue "
        "FROM users u LEFT JOIN orders o ON o.user_id=u.id AND o.kind!='topup' "
        "GROUP BY src ORDER BY users DESC LIMIT 30")
    cur = await db.get("currency")
    lines = [f"<code>{html.escape(r['src'])}</code>: {r['users']} польз. · {r['buyers']} покуп. · "
             f"{money(r['revenue'])}{cur}" for r in rows]
    name = (await c.bot.me()).username
    await out(c, "📈 <b>Источники трафика</b>\n\nСсылка с меткой: "
                 f"<code>https://t.me/{name}?start=МЕТКА</code>\n(латиница, цифры, _ и -, до 32 символов)\n\n"
                 + "\n".join(lines), kb(back()))


@router.callback_query(F.data == "ad:rv")
async def reviews(c: CallbackQuery):
    rs = await db.all("SELECT * FROM reviews ORDER BY id DESC LIMIT 15")
    avg = await db.one("SELECT AVG(rating) a, COUNT(*) n FROM reviews")
    lines = [f"{'⭐️' * r['rating']} #{r['order_id']} <code>{r['user_id']}</code>: {html.escape((r['text'] or '')[:100])}"
             for r in rs]
    head = (f"⭐️ <b>Отзывы</b>: {avg['n']}, средняя {avg['a'] or 0:.2f}\n"
            f"Оценки 4–5 публикуются в канал отзывов, 1–3 приходят вам.\n\n")
    await out(c, head + ("\n".join(lines) or "Пока нет"), kb(back()))


# ================= админы, журнал, бэкап =================

@router.callback_query(F.data == "ad:adm")
async def admins(c: CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[(f"🗑 {a['id']} · {a['role']} · {a['name'] or ''}", f"ad:admd:{a['id']}")]
            for a in await db.all("SELECT * FROM admins ORDER BY role")]
    await out(c, "👮 <b>Админы</b>\n\nВладельцы из .env (ADMIN_IDS) видят всё. Роли:\n"
                 "• <b>owner</b> — полный доступ\n• <b>operator</b> — только заказы и выводы\n\n"
                 "Нажмите, чтобы удалить.", kb(*rows, [("➕ Добавить", "ad:admadd")], back()))


@router.callback_query(F.data == "ad:admadd")
async def admin_add(c: CallbackQuery, state: FSMContext):
    await ask(c, state, "admin_new", "Пришлите: <code>ID роль [имя]</code>, например <code>123456 operator Аня</code>",
              "ad:adm")


@router.callback_query(F.data.startswith("ad:admd:"))
async def admin_delete(c: CallbackQuery, state: FSMContext):
    await db.run("DELETE FROM admins WHERE id=?", int(c.data[8:]))
    await admins(c, state)


@router.callback_query(F.data == "ad:log")
async def admin_log(c: CallbackQuery):
    rows = await db.all("SELECT * FROM admin_log ORDER BY id DESC LIMIT 30")
    lines = [f"{time.strftime('%d.%m %H:%M', time.localtime(r['ts']))} <code>{r['admin_id']}</code> "
             f"{html.escape(r['action'])}" for r in rows]
    await out(c, "📜 <b>Журнал действий</b>\n\n" + ("\n".join(lines) or "Пусто"), kb(back()))


@router.message(Command("fragment"))
async def fragment_check(m: Message, role: str):
    """Проверка настроек автовыдачи: кошелёк и баланс."""
    if role != "owner":
        return
    from .. import config
    lines = [f"Режим выдачи: <b>{await db.get('delivery_mode')}</b>",
             f"Seed: {'✅' if config.FRAGMENT_SEED else '❌ нет FRAGMENT_SEED'}",
             f"Cookies: {'✅' if config.FRAGMENT_COOKIES else '❌ нет FRAGMENT_COOKIES'}",
             f"API-ключ ({config.FRAGMENT_API_PROVIDER}): {'✅' if config.FRAGMENT_API_KEY else '❌ нет FRAGMENT_API_KEY'}",
             f"Версия кошелька: {config.FRAGMENT_WALLET_VERSION}"]
    try:
        addr, bal = await services.fragment_wallet()
        lines.append(f"\nКошелёк: <code>{addr}</code>\nБаланс: <b>{bal:g} TON</b>")
    except ImportError:
        lines.append("\n❌ Библиотека не установлена: <code>pip install fragment-api-py</code>")
    except Exception as e:
        lines.append(f"\n❌ {html.escape(type(e).__name__)}: {html.escape(str(e))[:300]}")
    await m.answer("\n".join(lines))


@router.callback_query(F.data == "ad:bkp")
async def backup_now(c: CallbackQuery):
    await c.answer("Готовлю бэкап…")
    await services.backup(c.bot, c.from_user.id)


# ================= ввод значений =================

def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _split_emoji(text: str) -> tuple[str, str]:
    """'⭐️ Купить' -> ('⭐️', 'Купить')."""
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and not any(ch.isalnum() for ch in parts[0]):
        return parts[0], parts[1]
    return "", text


async def _save_text(kind: str, ref, lang: str, text: str, sql: str):
    """Основной язык — в основную таблицу, остальные — в i18n."""
    if lang == (await db.languages())[0]:
        await db.run(sql, text, ref)
    else:
        await db.set_tr(kind, ref, lang, text)


@router.message(A.input)
async def admin_input(m: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind")
    text = (m.text or m.caption or "").strip()
    uid = m.from_user.id
    err = None
    if kind not in ("bc", "bc_time"):
        ref = data.get("key") or data.get("bid") or data.get("pid") or data.get("uid") or ""
        await db.log_admin(uid, f"input {kind} {ref}: {text[:80]}")

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
                await _save_text("screen", data["key"], data["lang"], new, "UPDATE screens SET text=? WHERE key=?")
                await state.clear()
                return await screen_view(m, data["key"], uid)

    elif kind == "scr_media":
        media = (("photo", m.photo[-1].file_id) if m.photo else ("video", m.video.file_id) if m.video
                 else ("animation", m.animation.file_id) if m.animation
                 else ("document", m.document.file_id) if m.document else None)
        if not media:
            err = "Пришлите фото, видео, GIF или файл"
        else:
            await db.run("UPDATE screens SET media_type=?, media_id=? WHERE key=?", *media, data["key"])
            if m.caption:
                lang, _ = await edit_lang(uid)
                await _save_text("screen", data["key"], lang, m.html_text, "UPDATE screens SET text=? WHERE key=?")
            await state.clear()
            return await screen_view(m, data["key"], uid)

    elif kind == "scr_title":
        await db.run("UPDATE screens SET title=? WHERE key=?", text[:40], data["key"])
        await state.clear()
        return await screen_view(m, data["key"], uid)

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
            return await screen_view(m, key, uid)

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
            return await button_view(m, cur.lastrowid, uid)

    elif kind == "btn_text":
        if not text:
            err = "Нужен текст"
        else:
            await _save_text("button", data["bid"], data["lang"], text[:64], "UPDATE buttons SET text=? WHERE id=?")

    elif kind == "btn_alert_tr":
        await db.set_tr("button_value", data["bid"], data["lang"], text[:200])

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
        templated = text.startswith("{")
        if action == "url" and not (templated or re.match(r"^(https?|tg)://", text)):
            err = "Нужна ссылка вида https://..."
        elif action == "webapp" and not (templated or text.startswith("https://")):
            err = "Mini App открывается только по https://"
        elif not text:
            err = "Пустое значение"
        else:
            await db.run("UPDATE buttons SET action=?, value=? WHERE id=?", action,
                         text[:200] if action == "alert" else text, data["bid"])

    elif kind == "pkg_new":
        p = text.split()
        pkind = "stars"
        if p and p[0].lower() == "p":
            pkind, p = "premium", p[1:]
        qty = int(p[0]) if p and p[0].isdigit() else 0
        price = _num(p[1]) if len(p) > 1 else None
        if qty <= 0 or (len(p) > 1 and (price is None or price <= 0)) or (pkind == "premium" and price is None):
            err = "Формат: <code>500 690</code> или <code>p 3 1290</code>"
        else:
            await db.run("INSERT INTO packages (kind, stars, price) VALUES (?, ?, ?)", pkind, qty, price)
            await state.clear()
            return await m.answer("✅ Пакет добавлен", reply_markup=kb([("💎 К пакетам", "ad:pk")]))

    elif kind == "pkg_price":
        price = None if text == "-" else _num(text)
        pkg = await db.one("SELECT kind FROM packages WHERE id=?", data["pid"])
        if text != "-" and (price is None or price <= 0):
            err = "Нужно число"
        elif price is None and pkg and pkg["kind"] == "premium":
            err = "У Premium цена обязательна"
        else:
            await db.run("UPDATE packages SET price=? WHERE id=?", price, data["pid"])
            await state.clear()
            return await m.answer("✅ Цена обновлена", reply_markup=kb([("💎 К пакетам", "ad:pk")]))

    elif kind == "set":
        value = "" if text == "-" else text
        if data["typ"] in ("int", "float") and value and (_num(value) is None or _num(value) < 0):
            err = "Нужно число"
        elif data["key"] == "delivery_mode" and value not in ("manual", "fragment", "api"):
            err = "Допустимо: manual, fragment или api"
        elif data["key"] == "levels" and value and not services.parse_levels(value):
            err = "Формат: <code>1000:2,5000:4</code>"
        elif data["key"] == "languages" and not value:
            err = "Нужен хотя бы один язык"
        else:
            if data["typ"] in ("int", "float") and value:
                value = value.replace(",", ".")
            await db.set(data["key"], value)
            await state.clear()
            return await m.answer("✅ Сохранено", reply_markup=kb([("⚙️ Назад", data["back"])]))

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

    elif kind == "admin_new":
        p = text.split(maxsplit=2)
        if len(p) < 2 or not p[0].isdigit() or p[1] not in ("owner", "operator"):
            err = "Формат: <code>ID owner|operator [имя]</code>"
        else:
            await db.run("INSERT OR REPLACE INTO admins VALUES (?, ?, ?)", int(p[0]), p[1], p[2] if len(p) > 2 else "")
            await state.clear()
            return await m.answer("✅ Админ добавлен", reply_markup=kb([("👮 К админам", "ad:adm")]))

    elif kind == "bc":
        await state.update_data(chat_id=m.chat.id, msg_id=m.message_id)
        segs = dict(services.SEGMENTS)
        if len(await db.languages()) > 1:
            names = await db.lang_names()
            segs.update({f"lang_{x}": f"Язык: {names.get(x, x)}" for x in await db.languages()})
        rows = [[(name, f"ad:bcs:{k}")] for k, name in segs.items()]
        return await m.answer("Кому отправить?", reply_markup=kb(*rows, [("✖️ Отмена", "ad:menu")]))

    elif kind == "bc_time":
        try:
            dt = datetime.strptime(text, "%d.%m %H:%M").replace(year=datetime.now().year)
            if dt < datetime.now():
                dt = dt.replace(year=dt.year + 1)
        except ValueError:
            err = "Формат: <code>25.12 18:00</code>"
        else:
            bid = await _schedule(uid, data, int(dt.timestamp()))
            await state.clear()
            return await m.answer(f"🕒 Рассылка #{bid} запланирована на {dt.strftime('%d.%m.%Y %H:%M')}",
                                  reply_markup=kb(back()))

    if err:
        return await m.answer(f"⚠️ {err}", reply_markup=kb([("✖️ Отмена", data.get("back", "ad:menu"))]))
    # по умолчанию — вернуться к редактируемой кнопке
    await state.clear()
    await button_view(m, data["bid"], uid)
