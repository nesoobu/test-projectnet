from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Меню"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или напишите сообщение...",
    )
