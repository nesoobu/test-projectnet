import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from . import config
from .db import db
from .handlers import admin, inline, user
from .middleware import UserMiddleware
from .services import background


def make_storage():
    if config.REDIS_URL:
        from aiogram.fsm.storage.redis import RedisStorage  # pip install redis
        return RedisStorage.from_url(config.REDIS_URL)
    return None  # MemoryStorage по умолчанию


async def run_webhook(bot: Bot, dp: Dispatcher):
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    await bot.set_webhook(config.WEBHOOK_URL + config.WEBHOOK_PATH, secret_token=config.WEBHOOK_SECRET or None,
                          allowed_updates=dp.resolve_used_update_types(), drop_pending_updates=False)
    app = web.Application()
    SimpleRequestHandler(dp, bot, secret_token=config.WEBHOOK_SECRET or None).register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, config.WEBAPP_HOST, config.WEBAPP_PORT).start()
    logging.info("Webhook на %s:%s%s", config.WEBAPP_HOST, config.WEBAPP_PORT, config.WEBHOOK_PATH)
    await asyncio.Event().wait()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в .env")
    await db.connect(config.DB_PATH)
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = make_storage()
    dp = Dispatcher(storage=storage) if storage else Dispatcher()
    mw = UserMiddleware()
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.include_routers(admin.router, inline.router, user.router)
    await bot.set_my_commands([BotCommand(command="start", description="Главное меню / Menu")])
    task = asyncio.create_task(background(bot))
    try:
        if config.WEBHOOK_URL:
            await run_webhook(bot, dp)
        else:
            await bot.delete_webhook()
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        task.cancel()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
