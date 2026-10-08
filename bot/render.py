"""Отрисовка экранов: текст + медиа + кнопки из БД."""
import html
import re

from aiogram import Bot
from aiogram.types import (CallbackQuery, CopyTextButton, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaAnimation, InputMediaDocument,
                           InputMediaPhoto, InputMediaVideo, Message, WebAppInfo)

from .db import db

PH = re.compile(r"\{(\w+)\}")
CAPTION_LIMIT = 1024
MEDIA_INPUT = {"photo": InputMediaPhoto, "video": InputMediaVideo,
               "animation": InputMediaAnimation, "document": InputMediaDocument}

_bot_username = ""


def fill(text: str, ctx: dict) -> str:
    return PH.sub(lambda m: str(ctx[m.group(1)]) if m.group(1) in ctx else m.group(0), text or "")


def money(x) -> str:
    x = round(float(x or 0), 2)
    return str(int(x)) if x == int(x) else f"{x:.2f}"


async def base_ctx(bot: Bot, user: dict) -> dict:
    global _bot_username
    if not _bot_username:
        _bot_username = (await bot.me()).username
    keys = ("rate", "currency", "min_stars", "max_stars", "support", "ref_percent", "topup_min")
    ctx = {k: html.escape(await db.get(k)) for k in keys}
    ctx.update(
        id=user["id"],
        name=html.escape(user.get("first_name") or "друг"),
        username=html.escape(user.get("username") or ""),
        balance=money(user.get("balance")),
        ref_link=f"https://t.me/{_bot_username}?start=r{user['id']}",
        bot_username=_bot_username,
    )
    return ctx


def make_button(b: dict, ctx: dict, callback_data: str | None = None, url: str | None = None):
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
        kw["url"] = value
    elif action == "webapp":
        kw["web_app"] = WebAppInfo(url=value)
    elif action == "copy":
        kw["copy_text"] = CopyTextButton(text=value[:256])
    elif action == "screen":
        kw["callback_data"] = f"s:{value}"
    elif action == "func":
        kw["callback_data"] = f"f:{value}"
    else:  # alert
        kw["callback_data"] = f"a:{b['id']}"
    return InlineKeyboardButton(text=text[:64] or "•", **kw)


async def sys_btn(key: str, ctx: dict, callback_data: str | None = None, url: str | None = None):
    b = await db.one("SELECT * FROM buttons WHERE screen='__sys__' AND value=?", key)
    if not b:
        b = {"id": 0, "emoji": "", "text": key}
    return make_button(b, ctx, callback_data=callback_data, url=url)


async def screen_buttons(key: str, ctx: dict) -> list[list[InlineKeyboardButton]]:
    rows: dict[int, list] = {}
    for b in await db.all("SELECT * FROM buttons WHERE screen=? AND enabled=1 ORDER BY row, pos, id", key):
        rows.setdefault(b["row"], []).append(make_button(b, ctx))
    return [rows[r] for r in sorted(rows)]


async def get_screen(key: str) -> dict:
    s = await db.one("SELECT * FROM screens WHERE key=?", key)
    return s or {"key": key, "text": key, "media_type": None, "media_id": None}


def _has_media(m: Message) -> bool:
    return bool(m.photo or m.video or m.animation or m.document)


async def show(event: Message | CallbackQuery, key: str, ctx: dict,
               top: list[list[InlineKeyboardButton]] | None = None,
               bottom: list[list[InlineKeyboardButton]] | None = None,
               edit: bool = True) -> Message:
    """Показать экран. При callback пытается отредактировать текущее сообщение."""
    s = await get_screen(key)
    text = fill(s["text"], ctx)
    rows = (top or []) + await screen_buttons(key, ctx) + (bottom or [])
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
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


async def send_screen(bot: Bot, chat_id: int, text: str, media_type, media_id, kb) -> Message:
    if media_id:
        sender = {"photo": bot.send_photo, "video": bot.send_video,
                  "animation": bot.send_animation, "document": bot.send_document}[media_type]
        if len(text) <= CAPTION_LIMIT:
            return await sender(chat_id, media_id, caption=text, reply_markup=kb)
        await sender(chat_id, media_id)
    return await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)


async def send_key(bot: Bot, chat_id: int, key: str, ctx: dict, top=None) -> Message:
    """Отправить экран по ключу (для уведомлений вне контекста апдейта)."""
    s = await get_screen(key)
    rows = (top or []) + await screen_buttons(key, ctx)
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    return await send_screen(bot, chat_id, fill(s["text"], ctx), s.get("media_type"), s.get("media_id"), kb)
