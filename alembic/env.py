from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.core.config import settings
from app.database.base import Base
import app.database.models
config = context.config
config.set_main_option('sqlalchemy.url', settings.database_url)
target_metadata = Base.metadata

def sync(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

async def async_run():
    e = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix='sqlalchemy.', poolclass=pool.NullPool)
    async with e.connect() as c:
        await c.run_sync(sync)
    await e.dispose()

def online():
    import asyncio
    asyncio.run(async_run())
if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    online()
