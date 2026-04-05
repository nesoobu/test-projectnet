from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n\n"
        "Я — Telegram-бот. Вот что я умею:\n"
        "• /help — список команд\n"
        "• /menu — меню с кнопками\n\n"
        "Или просто напиши мне что-нибудь!",
        reply_markup=main_menu_keyboard(),
    )
