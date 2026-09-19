from aiogram.filters import BaseFilter
from app.core.config import settings
from app.repositories.core import AdminRepository, UserRepository

class IsAdminOrOwner(BaseFilter):

    async def __call__(self, event, session):
        if not event.from_user:
            return False
        if event.from_user.id == settings.owner_telegram_id:
            return True
        u = await UserRepository(session).by_tg(event.from_user.id)
        return bool(u and u.is_active and await AdminRepository(session).by_user(u.id))

class IsOwner(BaseFilter):

    async def __call__(self, event):
        return bool(event.from_user and event.from_user.id == settings.owner_telegram_id)

class IsInactive(BaseFilter):

    async def __call__(self, event, session):
        u = await UserRepository(session).by_tg(event.from_user.id) if event.from_user else None
        return bool(u and (not u.is_active))
