"""Регистрация пользователя, бан, техработы, обязательная подписка, антифлуд."""
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from .config import ADMIN_IDS
from .db import db
from .render import base_ctx, show, sys_btn

FLOOD_DELAY = 0.4
SUB_CACHE_TTL = 120


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
        is_admin = tg.id in ADMIN_IDS
        data["is_admin"] = is_admin

        now = time.monotonic()
        if not is_admin and now - self.last.get(tg.id, 0) < FLOOD_DELAY:
            if isinstance(event, CallbackQuery):
                await event.answer()
            return
        self.last[tg.id] = now

        user, is_new = await db.upsert_user(tg.id, tg.username, tg.first_name)
        if is_new and isinstance(event, Message) and (event.text or "").startswith("/start r"):
            ref = event.text.split(maxsplit=1)[1][1:]
            if ref.isdigit() and int(ref) != tg.id and await db.user(int(ref)):
                await db.run("UPDATE users SET ref_id=? WHERE id=?", int(ref), tg.id)
                user["ref_id"] = int(ref)
        data["user"] = user

        if not is_admin:
            block = None
            if user["banned"]:
                block = "banned"
            elif await db.get_bool("maintenance"):
                block = "maintenance"
            if block:
                if isinstance(event, CallbackQuery):
                    await event.answer()
                await show(event, block, await base_ctx(event.bot, user), edit=False)
                return
            if not await self._check_sub(event, user):
                return
        return await handler(event, data)

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

