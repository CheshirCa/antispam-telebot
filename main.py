import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiohttp import web

from app.config import load_settings
from app.database import Database
from app.admin import router as admin_router
from app.handlers import cleanup_loop, router
from app.logging_config import configure_logging
from app.version import VERSION
from app.web import create_web_app


async def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    db = Database(settings.database_path)
    await db.connect()
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(admin_router)
    dispatcher.include_router(router)
    dispatcher["db"] = db
    dispatcher["settings"] = settings
    cleanup_task = asyncio.create_task(cleanup_loop(bot, db))
    web_runner = web.AppRunner(create_web_app(db, settings))
    await web_runner.setup()
    web_site = web.TCPSite(web_runner, settings.web_host, settings.web_port)
    await web_site.start()
    try:
        logger.info(
            "Starting anti-spam bot v%s; web panel: http://%s:%s",
            VERSION, settings.web_host, settings.web_port,
        )
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        await web_runner.cleanup()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
