import os
os.environ.setdefault('BOT_TOKEN', '123456:TEST')
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/test')
os.environ.setdefault('OWNER_TELEGRAM_ID', '1')

import uuid
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def db_factory():
    """Each test uses a fresh migrated schema; never drop the configured database."""
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not configured')
    schema = 'audit_' + uuid.uuid4().hex
    admin_engine = create_async_engine(url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}}, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            def migrate(sync_connection):
                config = Config('alembic.ini')
                config.attributes['connection'] = sync_connection
                command.upgrade(config, 'head')
            await connection.run_sync(migrate)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


@pytest.fixture
async def session(db_factory):
    async with db_factory() as value:
        yield value
        await value.rollback()
