from tests.test_dispatcher_e2e import bot_app  # noqa: F401 -- shared dispatcher fixture
from tests.test_runtime_audit import employee, lesson, pass_lesson
from app.services.admin_crud import AdminCrudService


async def test_retaking_passed_lesson_after_predecessor_republished(bot_app, db_factory):
    """A preserved pass must not claim the expanded active course is complete."""
    async with db_factory() as session:
        user = await employee(session)
        first = await lesson(session, 'Earlier topic', count=1)
        last = await lesson(session, 'Previously completed topic', count=1)
        admin = AdminCrudService(session)
        await admin.toggle_lesson(first.id)
        await pass_lesson(session, user, last)
        await admin.toggle_lesson(first.id)
        first_id, last_id = first.id, last.id
        await session.commit()

    await bot_app.send(callback=f'test:start:{last_id}')
    calls = await bot_app.send(callback=bot_app.callbacks('test:answer:')[0])
    assert 'Тест пройден' in str(calls)
    assert 'Все уроки пройдены' not in str(calls)
    assert f'lesson:{first_id}' in bot_app.callbacks('lesson:')
    assert 'Сначала пройдите все уроки' in str(await bot_app.send(text='Экзамен'))
