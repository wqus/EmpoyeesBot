import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation
from app.core.config import settings
from app.database.engine import dispose_engine
from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.bot.middlewares.guard import ErrorMiddleware, InputGuardMiddleware
from app.bot.middlewares.outgoing import TelegramLimitsMiddleware
from app.bot.handlers.user import router as user_router
from app.bot.handlers.admin.panel import router as admin_router
from app.bot.handlers.admin.owner import router as owner_router

def create_dispatcher():
    dp = Dispatcher(events_isolation=SimpleEventIsolation())
    db = DatabaseSessionMiddleware()
    dp.message.outer_middleware(ErrorMiddleware())
    dp.callback_query.outer_middleware(ErrorMiddleware())
    dp.message.outer_middleware(InputGuardMiddleware())
    dp.callback_query.outer_middleware(InputGuardMiddleware())
    dp.message.outer_middleware(db)
    dp.callback_query.outer_middleware(db)
    dp.include_router(owner_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    return dp


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    bot = Bot(settings.bot_token)
    bot.session.middleware(TelegramLimitsMiddleware())
    dp = create_dispatcher()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await dispose_engine()
if __name__ == '__main__':
    asyncio.run(main())
