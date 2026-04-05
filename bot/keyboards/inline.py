from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def menu_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ℹ️ Информация", callback_data="action_info"),
                InlineKeyboardButton(text="🏓 Ping", callback_data="action_ping"),
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="action_close"),
            ],
        ]
    )
