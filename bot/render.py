"""Отрисовка экранов: текст + медиа + кнопки из БД, с учётом языка пользователя."""
import html
import re
import time
from urllib.parse import quote, urlencode

from aiogram import Bot
from aiogram.types import (CallbackQuery, CopyTextButton, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaAnimation, InputMediaDocument,
                           InputMediaPhoto, InputMediaVideo, Message, WebAppInfo)

from .db import db

PH = re.compile(r"\{(\w+)\}")
TAG = re.compile(r"<[^>]+>")
CAPTION_LIMIT = 1024
MEDIA_INPUT = {"photo": InputMediaPhoto, "video": InputMediaVideo,
               "animation": InputMediaAnimation, "document": InputMediaDocument}

_bot_username = ""
_stats_cache: tuple[float, dict] = (0.0, {})


def fill(text: str, ctx: dict) -> str:
    return PH.sub(lambda m: str(ctx[m.group(1)]) if m.group(1) in ctx else m.group(0), text or "")


def money(x) -> str:
    x = round(float(x or 0), 2)
    return str(int(x)) if x == int(x) else f"{x:.2f}"


def fmt_int(n) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def mask(username: str | None) -> str:
    if not username:
        return "аноним"
    u = username.lstrip("@")
    return "@" + (u[:2] + "***" + u[-1:] if len(u) > 4 else u[:1] + "***")


async def bot_username(bot: Bot) -> str:
    global _bot_username
    if not _bot_username:
        _bot_username = (await bot.me()).username
    return _bot_username


async def public_stats() -> dict:
    """Публичные счётчики для главного экрана (кэш 60 сек)."""
    global _stats_cache
    if time.monotonic() - _stats_cache[0] > 60:
        r = await db.one("SELECT COALESCE(SUM(stars),0) s, COUNT(*) n FROM orders WHERE kind='stars' AND status='done'")
        n = await db.one("SELECT COUNT(*) n FROM orders WHERE kind IN ('stars','premium') AND status='done'")
        u = await db.one("SELECT COUNT(*) n FROM users")
        _stats_cache = (time.monotonic(), {"sold_stars": fmt_int(r["s"]), "done_orders": fmt_int(n["n"]),
                                           "users_count": fmt_int(u["n"])})
    return _stats_cache[1]


async def user_lang(user: dict | None) -> str:
    langs = await db.languages()
    lang = (user or {}).get("lang")
    return lang if lang in langs else langs[0]


async def webapp_link(bot: Bot, lang: str) -> str:
    url = await db.get("webapp_url")
    if not url:
        return ""
    rate = await db.get_float("rate")
    pk = []
    for p in await db.all("SELECT * FROM packages WHERE enabled=1 AND kind='stars' ORDER BY stars"):
        pk.append(f"{p['stars']}:{money(p['price'] if p['price'] is not None else p['stars'] * rate)}")
    q = {"bot": await bot_username(bot), "rate": money(rate), "cur": await db.get("currency"),
         "min": await db.get("min_stars"), "max": await db.get("max_stars"), "pk": ",".join(pk), "lang": lang}
    return url + ("&" if "?" in url else "?") + urlencode(q, quote_via=quote)


async def base_ctx(bot: Bot, user: dict) -> dict:
    keys = ("rate", "currency", "min_stars", "max_stars", "support", "ref_percent", "ref_percent2",
            "topup_min", "withdraw_min")
    ctx = {k: html.escape(await db.get(k)) for k in keys}
    lang = await user_lang(user)
    username = await bot_username(bot)
    ctx.update(await public_stats())
    ctx.update(
        _lang=lang,
        id=user["id"],
        name=html.escape(user.get("first_name") or "друг"),
        username=html.escape(user.get("username") or ""),
        balance=money(user.get("balance")),
        ref_link=f"https://t.me/{username}?start=r{user['id']}",
        bot_username=username,
        webapp_link=await webapp_link(bot, lang),
    )
    return ctx


async def localize_button(b: dict, lang: str) -> dict:
    if b.get("id") and lang != (await db.languages())[0]:
        t = await db.tr("button", b["id"], lang)
        if t:
            b = {**b, "text": t}
    return b


def make_button(b: dict, ctx: dict, callback_data: str | None = None, url: str | None = None):
    """Собрать кнопку. Возвращает None, если кнопка невалидна (например, пустая ссылка)."""
    text = fill(f"{b['emoji']} {b['text']}".strip() if b.get("emoji") else b["text"], ctx)
    kw = {}
    if b.get("icon_id"):
        kw["icon_custom_emoji_id"] = b["icon_id"]
    if b.get("style"):
        kw["style"] = b["style"]
    action, value = b.get("action"), fill(b.get("value") or "", ctx)
    if url:
        kw["url"] = url
    elif callback_data:
        kw["callback_data"] = callback_data
    elif action == "url":
        if not re.match(r"^(https?|tg)://", value):
            return None
        kw["url"] = value
    elif action == "webapp":
        if not value.startswith("https://"):
            return None
        kw["web_app"] = WebAppInfo(url=value)
    elif action == "copy":
        kw["copy_text"] = CopyTextButton(text=value[:256] or "-")
    elif action == "screen":
        kw["callback_data"] = f"s:{value}"
    elif action == "func":
        kw["callback_data"] = f"f:{value}"
    else:  # alert
        kw["callback_data"] = f"a:{b['id']}"
    return InlineKeyboardButton(text=text[:64] or "•", **kw)


async def sys_btn(key: str, ctx: dict, callback_data: str | None = None, url: str | None = None, copy: str | None = None):
    b = await db.one("SELECT * FROM buttons WHERE screen='__sys__' AND value=?", key)
    if not b:
        b = {"id": 0, "emoji": "", "text": key}
    b = await localize_button(b, ctx.get("_lang", "ru"))
    if copy is not None:
        b = {**b, "action": "copy", "value": copy}
    return make_button(b, ctx, callback_data=callback_data, url=url)


async def screen_buttons(key: str, ctx: dict) -> list[list[InlineKeyboardButton]]:
    rows: dict[int, list] = {}
    lang = ctx.get("_lang", "ru")
    for b in await db.all("SELECT * FROM buttons WHERE screen=? AND enabled=1 ORDER BY row, pos, id", key):
        btn = make_button(await localize_button(b, lang), ctx)
        if btn:
            rows.setdefault(b["row"], []).append(btn)
    return [rows[r] for r in sorted(rows)]


async def get_screen(key: str, lang: str | None = None) -> dict:
    s = await db.one("SELECT * FROM screens WHERE key=?", key)
    if not s:
        return {"key": key, "text": key, "media_type": None, "media_id": None}
    if lang and lang != (await db.languages())[0]:
        t = await db.tr("screen", key, lang)
        if t:
            s["text"] = t
    return s


async def screen_plain(key: str, ctx: dict) -> str:
    """Текст экрана без HTML — для всплывающих уведомлений."""
    s = await get_screen(key, ctx.get("_lang"))
    return html.unescape(TAG.sub("", fill(s["text"], ctx)))[:200]


def _has_media(m: Message) -> bool:
    return bool(m.photo or m.video or m.animation or m.document)


async def show(event: Message | CallbackQuery, key: str, ctx: dict,
               top: list[list[InlineKeyboardButton]] | None = None,
               bottom: list[list[InlineKeyboardButton]] | None = None,
               edit: bool = True) -> Message:
    """Показать экран. При callback пытается отредактировать текущее сообщение."""
    s = await get_screen(key, ctx.get("_lang"))
    text = fill(s["text"], ctx)
    rows = [r for r in (top or []) + await screen_buttons(key, ctx) + (bottom or []) if r]
    rows = [[b for b in r if b] for r in rows]
    kb = InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r]) if rows else None
    media_type, media_id = s.get("media_type"), s.get("media_id")

    if isinstance(event, CallbackQuery):
        msg = event.message
        if edit and msg:
            try:
                if not media_id and not _has_media(msg):
                    return await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
                if media_id and _has_media(msg) and len(text) <= CAPTION_LIMIT:
                    media = MEDIA_INPUT[media_type](media=media_id, caption=text)
                    return await msg.edit_media(media, reply_markup=kb)
            except Exception:
                pass
            try:
                await msg.delete()
            except Exception:
                pass
        chat_id = event.from_user.id
    else:
        chat_id = event.chat.id
    return await send_screen(event.bot, chat_id, text, media_type, media_id, kb)


async def send_screen(bot: Bot, chat_id, text: str, media_type, media_id, kb) -> Message:
    if media_id:
        sender = {"photo": bot.send_photo, "video": bot.send_video,
                  "animation": bot.send_animation, "document": bot.send_document}[media_type]
        if len(text) <= CAPTION_LIMIT:
            return await sender(chat_id, media_id, caption=text, reply_markup=kb)
        await sender(chat_id, media_id)
    return await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)


async def send_key(bot: Bot, chat_id, key: str, ctx: dict, top=None, with_buttons: bool = True) -> Message:
    """Отправить экран по ключу (для уведомлений и постов в каналы)."""
    s = await get_screen(key, ctx.get("_lang"))
    rows = [[b for b in r if b] for r in (top or []) + (await screen_buttons(key, ctx) if with_buttons else [])]
    rows = [r for r in rows if r]
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    return await send_screen(bot, chat_id, fill(s["text"], ctx), s.get("media_type"), s.get("media_id"), kb)
