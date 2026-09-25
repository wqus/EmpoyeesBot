import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database.base import Base
import app.database.models
from app.database.models import Studio, User, Lesson, LessonMedia, LessonQuestion, LessonAnswerOption, ExamQuestion, ExamAnswerOption, MediaType, LessonProgressStatus
from app.services.core import LearningService, LessonTestService, ExamService
from app.services.admin_crud import AdminCrudService
URL = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='TEST_DATABASE_URL is not configured')

@pytest.mark.asyncio
async def test_registration_learning_test_unlock_and_exam(session):
    studio = Studio(name='Studio A', is_active=True)
    session.add(studio)
    await session.flush()
    user = User(telegram_id=1001, full_name='Test User', studio_id=studio.id, is_active=True)
    session.add(user)
    await session.flush()
    admin = AdminCrudService(session)
    first = await admin.create_lesson('Lesson 1')
    await admin.add_lesson_text(first.id, 'Theory 1')
    await admin.add_lesson_question(first.id, '2+2?', ['4', '5'], 0)
    await admin.toggle_lesson(first.id)
    second = await admin.create_lesson('Lesson 2')
    await admin.add_lesson_text(second.id, 'Theory 2')
    await admin.add_lesson_question(second.id, '3+3?', ['6', '7'], 0)
    await admin.toggle_lesson(second.id)
    learning = LearningService(session)
    progress = await learning.list(user.id)
    assert [p.status for p in progress] == [LessonProgressStatus.AVAILABLE, LessonProgressStatus.LOCKED]
    qs = await LessonTestService(session).questions(first.id)
    result = await LessonTestService(session).finish(user.id, first.id, [(qs[0].id, qs[0].options[0].id)])
    assert result == (1, 1, True)
    progress = await learning.list(user.id)
    assert progress[1].status == LessonProgressStatus.AVAILABLE
    qs = await LessonTestService(session).questions(second.id)
    await LessonTestService(session).finish(user.id, second.id, [(qs[0].id, qs[0].options[0].id)])
    for i in range(30):
        topic_id = second.id if i == 0 else first.id
        q = ExamQuestion(lesson_id=topic_id, text=f'Exam {i}', is_active=True)
        session.add(q)
        await session.flush()
        session.add_all([ExamAnswerOption(question_id=q.id, text='yes', is_correct=True, position=1), ExamAnswerOption(question_id=q.id, text='no', is_correct=False, position=2)])
    await session.flush()
    exam = ExamService(session)
    attempt = await exam.start(user.id)
    slots = await exam.e.answers(attempt.id)
    assert {slot.question.lesson_id for slot in slots} == {first.id, second.id}
    for _ in range(30):
        slot = await exam.current(user.id, attempt.id)
        assert slot is not None
        correct = next((x for x in slot.question.options if x.is_correct))
        await exam.answer(user.id, attempt.id, slot.question_id, correct.id)
    finished = await exam.finish(user.id, attempt.id)
    assert finished.correct_count == 30
    assert finished.passed is True

@pytest.mark.asyncio
async def test_published_lesson_cannot_be_structurally_edited(session):
    studio = Studio(name='Studio A', is_active=True)
    session.add(studio)
    await session.flush()
    admin = AdminCrudService(session)
    lesson = await admin.create_lesson('Published')
    await admin.add_lesson_text(lesson.id, 'Body')
    await admin.add_lesson_question(lesson.id, 'Q', ['A', 'B'], 0)
    await admin.toggle_lesson(lesson.id)
    with pytest.raises(Exception):
        await admin.add_lesson_text(lesson.id, 'Mutation')

@pytest.mark.asyncio
async def test_owner_invite_without_employee_row_and_admin_accept(session):
    from app.core.config import settings
    from app.services.admin import InviteService
    from app.database.models import Admin, AdminInvite
    from sqlalchemy import select

    studio = Studio(name='Invite Studio', is_active=True)
    session.add(studio)
    await session.flush()
    raw = await InviteService(session).create(settings.owner_telegram_id, None)
    invite = await session.scalar(select(AdminInvite).order_by(AdminInvite.id.desc()))
    assert invite is not None
    assert invite.created_by_user_id is None

    user = User(telegram_id=2002, full_name='Invited Admin', studio_id=studio.id, is_active=True)
    session.add(user)
    await session.flush()
    await InviteService(session).accept(raw, user.id)
    admin = await session.scalar(select(Admin).where(Admin.user_id == user.id))
    assert admin is not None
    assert invite.used_by_user_id == user.id
