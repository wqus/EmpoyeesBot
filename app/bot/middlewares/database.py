from aiogram import BaseMiddleware
from app.database.engine import async_session_factory

class DatabaseSessionMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        async with async_session_factory() as s:
            data['session'] = s
            try:
                result = await handler(event, data)
                if s.in_transaction():
                    await s.commit()
                return result
            except Exception:
                if s.in_transaction():
                    await s.rollback()
                raise
