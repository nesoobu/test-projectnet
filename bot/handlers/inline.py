"""Inline-режим: @bot 500 в любом чате → карточка с ценой и кнопкой покупки.
Включите в @BotFather: /setinline."""
from aiogram import Router
from aiogram.types import (InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent)

from .. import services
from ..db import db
from ..render import bot_username, money

router = Router()


@router.inline_query()
async def inline(q: InlineQuery):
    lo, hi = await db.get_int("min_stars"), await db.get_int("max_stars")
    cur = await db.get("currency")
    username = await bot_username(q.bot)
    text = q.query.strip().replace(" ", "")
    if text.isdigit() and lo <= int(text) <= hi:
        amounts = [int(text)]
    else:
        amounts = [p["stars"] for p in await db.all("SELECT stars FROM packages WHERE enabled=1 AND kind='stars' "
                                                     "ORDER BY stars LIMIT 10")]
    results = []
    for n in amounts:
        price = money(await services.base_price("stars", n))
        kb = Kb(inline_keyboard=[[Btn(text=f"⭐️ Купить {n} за {price}{cur}", url=f"https://t.me/{username}?start=buy{n}")],
                                 [Btn(text="🎁 Подарить", url=f"https://t.me/{username}?start=gift{n}")]])
        results.append(InlineQueryResultArticle(
            id=f"s{n}", title=f"{n} ⭐️ — {price} {cur}",
            description="Telegram Stars без комиссии App Store / Google Play",
            input_message_content=InputTextMessageContent(
                message_text=f"⭐️ <b>{n} Telegram Stars</b> всего за <b>{price} {cur}</b>\n\nПокупка в @{username}"),
            reply_markup=kb))
    await q.answer(results, cache_time=60, is_personal=False)
