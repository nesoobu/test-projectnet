"""Регистрация пользователя, рефералы, UTM, язык, бан, техработы, обязательная подписка, антифлуд."""
import re
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from .config import ADMIN_IDS
from .db import db
from .render import base_ctx, show, sys_btn

FLOOD_DELAY = 0.4
SUB_CACHE_TTL = 120
SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class UserMiddleware(BaseMiddleware):
    def __init__(self):
        self.last: dict[int, float] = {}
        self.subscribed: dict[int, float] = {}

    async def __call__(self, handler, event, data):
        tg = event.from_user
        if not tg or tg.is_bot:
            return
        if isinstance(event, Message) and event.chat.type != "private":
            return
        role = await db.admin_role(tg.id, ADMIN_IDS)
        data["role"] = role

        now = time.monotonic()
        if not role and now - self.last.get(tg.id, 0) < FLOOD_DELAY:
            if isinstance(event, CallbackQuery):
                await event.answer()
            return
        self.last[tg.id] = now

        user, is_new = await db.upsert_user(tg.id, tg.username, tg.first_name)
        if is_new:
            await self._on_new_user(event, tg, user)
        data["user"] = user

        if not role:
            block = "banned" if user["banned"] else "maintenance" if await db.get_bool("maintenance") else None
            if block:
                if isinstance(event, CallbackQuery):
                    await event.answer()
                await show(event, block, await base_ctx(event.bot, user), edit=False)
                return
            if not await self._check_sub(event, user):
                return
        return await handler(event, data)

    async def _on_new_user(self, event, tg, user: dict):
        langs = await db.languages()
        code = (tg.language_code or "")[:2]
        lang = code if code in langs else langs[0]
        ref_id, source = None, None
        if isinstance(event, Message) and (event.text or "").startswith("/start "):
            payload = event.text.split(maxsplit=1)[1].strip()
            if payload.startswith("r") and payload[1:].isdigit():
                ref = int(payload[1:])
                if ref != tg.id and await db.user(ref):
                    ref_id = ref
            elif not payload.startswith(("buy", "gift")) and SOURCE_RE.match(payload):
                source = payload  # UTM-метка: t.me/bot?start=<source>
        await db.run("UPDATE users SET lang=?, ref_id=?, source=? WHERE id=?", lang, ref_id, source, tg.id)
        user.update(lang=lang, ref_id=ref_id, source=source)

    async def _check_sub(self, event, user) -> bool:
        channel = await db.get("required_channel")
        if not channel:
            return True
        uid = user["id"]
        if time.monotonic() - self.subscribed.get(uid, 0) < SUB_CACHE_TTL:
            return True
        try:
            m = await event.bot.get_chat_member(channel, uid)
            ok = m.status not in ("left", "kicked")
        except Exception:
            ok = True  # бот не админ в канале — не блокируем пользователей
        if ok:
            self.subscribed[uid] = time.monotonic()
            return True
        ctx = await base_ctx(event.bot, user)
        rows = []
        if channel.startswith("@"):
            rows.append([await sys_btn("subscribe_channel", ctx, url=f"https://t.me/{channel[1:]}")])
        rows.append([await sys_btn("subscribe_check", ctx, callback_data="f:menu")])
        if isinstance(event, CallbackQuery):
            await event.answer()
        await show(event, "subscribe", ctx, top=rows)
        return False
