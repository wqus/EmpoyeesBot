import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.database.models import ExamAttempt, Lesson, LessonProgress, LessonProgressStatus
from tests.test_runtime_audit import employee, lesson


async def test_migration_roundtrip_and_model_parity(db_factory):
    async with db_factory.kw['bind'].begin() as connection:
        def check(sync):
            context = MigrationContext.configure(sync, opts={'compare_type': True})
            assert compare_metadata(context, Base.metadata) == []
            config = Config('alembic.ini')
            config.attributes['connection'] = sync
            command.downgrade(config, 'base')
            assert inspect(sync).get_table_names() == ['alembic_version']
            command.upgrade(config, 'head')
            assert compare_metadata(MigrationContext.configure(sync), Base.metadata) == []
        await connection.run_sync(check)


async def test_constraints_are_enforced_by_postgres(session):
    user = await employee(session)
    item = await lesson(session)
    invalid = [
        Lesson(title='Duplicate position', position=item.position),
        Lesson(title='Negative position', position=-1),
        LessonProgress(user_id=999999, lesson_id=item.id, status=LessonProgressStatus.LOCKED),
        ExamAttempt(user_id=user.id, total_count=30, correct_count=31),
    ]
    for row in invalid:
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(row)
                await session.flush()
    session.add(ExamAttempt(user_id=user.id, total_count=30, correct_count=0))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(ExamAttempt(user_id=user.id, total_count=30, correct_count=0))
            await session.flush()
    assert await session.scalar(text('SELECT 1')) == 1


async def test_transaction_failure_after_flush_leaves_no_half_entities(db_factory):
    async with db_factory() as s:
        with pytest.raises(RuntimeError):
            async with s.begin():
                await employee(s)
                raise RuntimeError('after flush')
    from app.database.models import Studio, User
    from sqlalchemy import func
    async with db_factory() as s:
        assert await s.scalar(select(func.count(User.id))) == 0
        assert await s.scalar(select(func.count(Studio.id))) == 0
