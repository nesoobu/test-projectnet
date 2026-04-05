from aiogram import Router, F
from aiogram.types import Message

from bot.keyboards.inline import menu_inline_keyboard

router = Router()


@router.message(F.text == "📋 Меню")
async def reply_menu(message: Message) -> None:
    await message.answer(
        "📋 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=menu_inline_keyboard(),
    )


@router.message(F.text == "❓ Помощь")
async def reply_help(message: Message) -> None:
    help_text = (
        "📖 <b>Доступные команды:</b>\n\n"
        "/start — запустить бота\n"
        "/help — показать справку\n"
        "/menu — открыть меню с inline-кнопками\n\n"
        "Также я повторяю любое текстовое сообщение 🦜"
    )
    await message.answer(help_text)
