from collections import Counter
import pytest
from sqlalchemy import select
from app.core.exceptions import AppError
from app.database.models import ExamAnswer, ExamAttempt, LessonProgress, LessonProgressStatus
from app.services.admin_crud import AdminCrudService
from app.services.core import ExamService, LearningService, ResultService
from tests.test_runtime_audit import employee, lesson


async def test_100_exam_samples_cover_all_topics_and_resume(session):
    user = await employee(session)
    admin = AdminCrudService(session)
    lessons = [await lesson(session, f'Topic {i}', count=1) for i in range(10)]
    await LearningService(session).list(user.id)
    for p in (await session.scalars(select(LessonProgress))).all():
        p.status = LessonProgressStatus.PASSED
    for item in lessons:
        for i in range(5):
            q = await admin.create_exam_question(item.id, f'Q {item.id}-{i}', ['Yes', 'No'], 0)
            await admin.toggle_exam_question(q.id)
    await session.flush()
    samples = set()
    for _ in range(100):
        checkpoint = await session.begin_nested()
        exam = ExamService(session)
        a = await exam.start(user.id)
        rows = await exam.e.answers(a.id)
        assert len(rows) == 30
        assert len({r.question_id for r in rows}) == 30
        assert {r.question.lesson_id for r in rows} == {x.id for x in lessons}
        assert (await exam.start(user.id)).id == a.id
        samples.add(tuple(r.question_id for r in rows))
        await checkpoint.rollback()
    assert len(samples) > 95


@pytest.mark.parametrize('count', [0, 29])
async def test_insufficient_bank_is_business_error(session, count):
    user = await employee(session)
    item = await lesson(session, count=1)
    await LearningService(session).list(user.id)
    p = await session.scalar(select(LessonProgress))
    p.status = LessonProgressStatus.PASSED
    admin = AdminCrudService(session)
    for i in range(count):
        q = await admin.create_exam_question(item.id, f'Q {i}', ['Yes', 'No'], 0)
        await admin.toggle_exam_question(q.id)
    with pytest.raises(AppError):
        await ExamService(session).start(user.id)


async def test_exam_resume_after_new_connection_and_disabled_user(db_factory):
    from tests.test_concurrency import prepare_exam
    uid = await prepare_exam(db_factory)
    async with db_factory() as s:
        exam = ExamService(s)
        a = await exam.start(uid)
        slot = await exam.current(uid, a.id)
        aid = a.id
        await exam.answer(uid, aid, slot.question_id, slot.question.options[0].id)
        await s.commit()
    async with db_factory() as s:
        exam = ExamService(s)
        assert (await exam.start(uid)).id == aid
        assert (await exam.current(uid, aid)).position == 2
        await AdminCrudService(s).toggle_user(uid)
        await s.commit()
    async with db_factory() as s:
        with pytest.raises(AppError):
            await ExamService(s).current(uid, aid)
