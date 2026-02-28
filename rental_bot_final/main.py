"""
main.py — Start the bot.

Just run:  python main.py
That's it. No webhook, no Redis, no Docker needed.

Uses PostgreSQL for concurrent-safe database access.
"""
import asyncio
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from config import BOT_TOKEN
from database import init_db, close_db
from handlers import main_router
from middlewares import RoleMiddleware


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env file!")

    # Set up database pool
    await init_db()
    logger.info("✅ Database ready")

    # Bot + Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())

    # Routers
    dp.include_router(main_router)

    logger.info("🤖 Bot started (polling)")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        await close_db()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    logger.add("logs/bot.log", rotation="10 MB", retention="7 days", level="INFO")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
