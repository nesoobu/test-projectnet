from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.keyboards.inline import menu_inline_keyboard

router = Router()


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(
        "📋 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=menu_inline_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action_info")
async def callback_info(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "ℹ️ Я — шаблонный бот на aiogram 3.\n"
        "Вы можете расширить меня, добавив новые хэндлеры в <code>bot/handlers/</code>.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "action_ping")
async def callback_ping(callback: CallbackQuery) -> None:
    await callback.answer("🏓 Pong!", show_alert=True)


@router.callback_query(F.data == "action_close")
async def callback_close(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer()
