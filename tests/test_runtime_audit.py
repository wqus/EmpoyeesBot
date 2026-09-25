"""Behavioral regressions found by the September 2026 audit."""
import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.database.models import (
    Studio, User, Lesson, LessonProgressStatus, MaterialCategory, Material,
    ExamAnswer, ExamAttempt,
)
from app.repositories.core import MaterialRepository
from app.services.core import LearningService, LessonTestService, RegistrationService
from app.services.admin_crud import AdminCrudService


async def employee(session, tg=1001):
    studio = Studio(name=f'Studio {tg}', is_active=True)
    session.add(studio)
    await session.flush()
    return await RegistrationService(session).register(tg, 'Test Employee', studio.id)


async def lesson(session, title='Lesson', count=5):
    service = AdminCrudService(session)
    item = await service.create_lesson(title)
    await service.add_lesson_text(item.id, 'Theory')
    for i in range(count):
        await service.add_lesson_question(item.id, f'Question {i}', ['Yes', 'No'], 0)
    await service.toggle_lesson(item.id)
    return item


async def pass_lesson(session, user, item, correct=5):
    questions = await LessonTestService(session).questions(item.id)
    return await LessonTestService(session).finish(user.id, item.id, [
        (q.id, next(o.id for o in q.options if o.is_correct == (i < correct)))
        for i, q in enumerate(questions)
    ])


async def test_hidden_predecessor_unlocks_existing_progress(session):
    user = await employee(session)
    first = await lesson(session, 'First')
    second = await lesson(session, 'Second')
    await LearningService(session).list(user.id)
    await AdminCrudService(session).toggle_lesson(first.id)
    progress = await LearningService(session).list(user.id)
    assert [(p.lesson_id, p.status) for p in progress] == [(second.id, LessonProgressStatus.AVAILABLE)]


async def test_republished_predecessor_relocks_unpassed_successor(session):
    user = await employee(session)
    first = await lesson(session, 'First')
    second = await lesson(session, 'Second')
    await AdminCrudService(session).toggle_lesson(first.id)
    await LearningService(session).list(user.id)
    await AdminCrudService(session).toggle_lesson(first.id)
    with pytest.raises(AppError):
        await LearningService(session).lesson(user.id, second.id)


async def test_hidden_category_denies_direct_material_access(session):
    category = MaterialCategory(name='Hidden', slug='hidden', position=1, is_active=False)
    session.add(category)
    await session.flush()
    item = Material(category_id=category.id, title='Secret', content='Body', position=1, is_active=True)
    session.add(item)
    await session.flush()
    assert await MaterialRepository(session).materials(category.id) == []
    assert await MaterialRepository(session).material(item.id) is None


async def test_registration_rejects_long_name_as_business_error(session):
    studio = Studio(name='Studio', is_active=True)
    session.add(studio)
    await session.flush()
    with pytest.raises(AppError):
        await RegistrationService(session).register(55, 'a' * 256, studio.id)


async def test_hidden_lesson_cannot_finish_test(session):
    user = await employee(session)
    item = await lesson(session)
    await LearningService(session).list(user.id)
    await AdminCrudService(session).toggle_lesson(item.id)
    with pytest.raises(AppError):
        await pass_lesson(session, user, item)


@pytest.mark.parametrize('score,passed', [(3, False), (4, True), (5, True)])
async def test_actual_lesson_threshold_and_unlock(session, score, passed):
    user = await employee(session)
    first = await lesson(session, 'First')
    second = await lesson(session, 'Second')
    await LearningService(session).list(user.id)
    assert await pass_lesson(session, user, first, score) == (score, 5, passed)
    progress = await LearningService(session).list(user.id)
    assert progress[1].lesson_id == second.id
    assert (progress[1].status == LessonProgressStatus.AVAILABLE) is passed


@pytest.mark.parametrize('operation', ['edit_exam_text', 'change_exam_lesson'])
async def test_exam_history_text_and_topic_are_immutable(session, operation):
    user = await employee(session)
    first = await lesson(session, 'First')
    second = await lesson(session, 'Second')
    admin = AdminCrudService(session)
    q = await admin.create_exam_question(first.id, 'Original', ['Yes', 'No'], 0)
    attempt = ExamAttempt(user_id=user.id, total_count=30, correct_count=0)
    session.add(attempt)
    await session.flush()
    session.add(ExamAnswer(attempt_id=attempt.id, question_id=q.id, position=1))
    await session.flush()
    with pytest.raises(AppError):
        await getattr(admin, operation)(q.id, 'Changed' if operation == 'edit_exam_text' else second.id)
