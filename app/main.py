import asyncio, logging
from aiogram import Bot, Dispatcher
from app.core.config import settings
from app.database.engine import dispose_engine
from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.bot.handlers.user import router as user_router
from app.bot.handlers.admin.panel import router as admin_router
from app.bot.handlers.admin.owner import router as owner_router

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    db = DatabaseSessionMiddleware()
    dp.message.outer_middleware(db)
    dp.callback_query.outer_middleware(db)
    dp.include_router(owner_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await dispose_engine()
if __name__ == '__main__':
    asyncio.run(main())
