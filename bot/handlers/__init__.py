from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.help import router as help_router
from bot.handlers.echo import router as echo_router
from bot.handlers.menu import router as menu_router
from bot.handlers.buttons import router as buttons_router


def get_all_routers() -> list[Router]:
    return [
        start_router,
        help_router,
        menu_router,
        buttons_router,
        echo_router,  # echo must be last — it catches all text messages
    ]
