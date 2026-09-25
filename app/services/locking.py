"""Transaction-scoped PostgreSQL locks; callers commit/rollback the unit of work."""
from functools import wraps

from sqlalchemy import select, text

from app.core.exceptions import AppError
from app.database.models import User


async def catalog_lock(session, *, shared=False):
    function = 'pg_advisory_xact_lock_shared' if shared else 'pg_advisory_xact_lock'
    await session.execute(text(f'SELECT {function}(73421, 1)'))


async def active_employee(session, user_id):
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user or not user.is_active:
        raise AppError('Сотрудник не найден или доступ отключён')
    return user


def catalog_write(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        await catalog_lock(self.s)
        return await method(self, *args, **kwargs)
    return wrapped
