from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "📖 <b>Доступные команды:</b>\n\n"
        "/start — запустить бота\n"
        "/help — показать это сообщение\n"
        "/menu — открыть меню с inline-кнопками\n\n"
        "Также я повторяю любое текстовое сообщение 🦜"
    )
    await message.answer(help_text, parse_mode="HTML")
