# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from database import init_db
from handlers import router as handler_router
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)

async def main():
    # Initialize Database
    init_db()

    # Bot Setup
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Include Routers
    dp.include_router(handler_router)

    # Start Polling
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())