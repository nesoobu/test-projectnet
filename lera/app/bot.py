"""Бот Леры: вход в мини-апп, рефералки, оплата Stars.  Запуск: python -m app.bot"""
import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, Message, MenuButtonWebApp,
                           PreCheckoutQuery, WebAppInfo)

from . import config, db
from .main import apply_payment, ensure_user

dp = Dispatcher()


def open_kb(text: str = "Открыть Леру", start: str | None = None) -> InlineKeyboardMarkup:
    url = config.WEBAPP_URL + (f"?s={start}" if start else "")
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]])


@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    u = m.from_user
    # t.me/<bot>?start=s12 — приглашение в отряд, ref_<id> — рефералка
    deep = command.args if command.args and re.fullmatch(r"[smptc]\d+|likes|duet|home|pass", command.args) else None
    await ensure_user({"id": u.id, "username": u.username, "first_name": u.first_name,
                       "language_code": u.language_code}, command.args)
    await m.answer(
        "<b>Лера на связи.</b>\n\n"
        "Найду тиммейта под твою роль и ранг, соберу отряд на катку, "
        "а между играми — лента, гача и топы.\n\n"
        "Жми кнопку — и погнали.",
        reply_markup=open_kb(start=deep), parse_mode="HTML")


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def paid(m: Message):
    p = m.successful_payment
    payload_uid = p.invoice_payload.split(":")[-1]
    uid = int(payload_uid) if payload_uid.isdigit() else m.from_user.id
    if await apply_payment(p.telegram_payment_charge_id, uid, p.invoice_payload, p.total_amount):
        await m.answer("Оплата прошла, спасибо! Всё уже начислено ✨", reply_markup=open_kb("Вернуться к Лере"))


async def main():
    logging.basicConfig(level=logging.INFO)
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан в .env")
    await db.connect()
    bot = Bot(config.BOT_TOKEN)
    if config.WEBAPP_URL:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Лера", web_app=WebAppInfo(url=config.WEBAPP_URL)))
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
