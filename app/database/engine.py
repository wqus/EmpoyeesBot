from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
engine = create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def dispose_engine():
    await engine.dispose()
