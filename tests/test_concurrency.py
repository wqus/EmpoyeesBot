import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.database.models import Admin, AdminInvite, ExamAnswer, ExamAttempt, LessonProgress, LessonProgressStatus
from app.services.admin import InviteService
from app.services.admin_crud import AdminCrudService
from app.services.core import ExamService, LearningService, RegistrationService
from tests.test_runtime_audit import employee, lesson


async def prepare_exam(db_factory):
    async with db_factory() as s:
        user = await employee(s)
        item = await lesson(s, count=1)
        await LearningService(s).list(user.id)
        progress = await s.scalar(select(LessonProgress))
        progress.status = LessonProgressStatus.PASSED
        admin = AdminCrudService(s)
        for i in range(35):
            q = await admin.create_exam_question(item.id, f'Exam {i}', ['Yes', 'No'], 0)
            await admin.toggle_exam_question(q.id)
        uid = user.id
        await s.commit()
    return uid


async def test_concurrent_exam_start_returns_one_attempt(db_factory):
    uid = await prepare_exam(db_factory)
    async def start():
        async with db_factory() as s:
            value = await ExamService(s).start(uid)
            await s.commit()
            return value.id
    ids = await asyncio.gather(start(), start(), start())
    assert len(set(ids)) == 1
    async with db_factory() as s:
        assert await s.scalar(select(func.count(ExamAttempt.id))) == 1
        assert await s.scalar(select(func.count(ExamAnswer.id))) == 30


async def test_concurrent_exam_answers_and_foreign_attempt(db_factory):
    uid = await prepare_exam(db_factory)
    async with db_factory() as s:
        exam = ExamService(s)
        a = await exam.start(uid)
        slot = await exam.current(uid, a.id)
        aid, qid, oid = a.id, slot.question_id, slot.question.options[0].id
        other = await employee(s, 2002)
        other_id = other.id
        await s.commit()
    async def answer(user_id):
        async with db_factory() as s:
            try:
                await ExamService(s).answer(user_id, aid, qid, oid)
                await s.commit()
                return True
            except AppError:
                await s.rollback()
                return False
    assert await answer(other_id) is False
    assert sorted(await asyncio.gather(answer(uid), answer(uid))) == [False, True]
    async with db_factory() as s:
        assert await s.scalar(select(func.count(ExamAnswer.id)).where(ExamAnswer.selected_option_id.is_not(None))) == 1


async def test_concurrent_invite_accept_is_one_use(db_factory):
    async with db_factory() as s:
        first = await employee(s, 1001)
        second = await employee(s, 2002)
        ids = [first.id, second.id]
        raw = await InviteService(s).create(1)
        await s.commit()
    async def accept(uid):
        async with db_factory() as s:
            try:
                await InviteService(s).accept(raw, uid)
                await s.commit()
                return True
            except AppError:
                await s.rollback()
                return False
    assert sorted(await asyncio.gather(*(accept(uid) for uid in ids))) == [False, True]
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Admin.id))) == 1


async def test_concurrent_content_creation_preserves_positions(db_factory):
    async def create(i):
        async with db_factory() as s:
            obj = await AdminCrudService(s).create_lesson(f'Lesson {i}')
            await s.commit()
            return obj.position
    assert sorted(await asyncio.gather(*(create(i) for i in range(8)))) == list(range(1, 9))


async def test_concurrent_registration_and_progress(db_factory):
    async with db_factory() as s:
        from app.database.models import Studio
        studio = await AdminCrudService(s).create_studio('Main')
        sid = studio.id
        await lesson(s)
        await s.commit()
    async def register():
        async with db_factory() as s:
            try:
                u = await RegistrationService(s).register(1001, 'Employee', sid)
                await s.commit()
                return u.id
            except AppError:
                return None
    results = await asyncio.gather(register(), register())
    uid = next(i for i in results if i)
    assert results.count(None) == 1
    async def progress():
        async with db_factory() as s:
            await LearningService(s).list(uid)
            await s.commit()
    await asyncio.gather(progress(), progress())
    async with db_factory() as s:
        assert await s.scalar(select(func.count(LessonProgress.id))) == 1


@pytest.mark.parametrize('state', ['expired', 'revoked', 'used'])
async def test_unusable_invites_preserve_admin_count(db_factory, state):
    async with db_factory() as s:
        u = await employee(s)
        raw = await InviteService(s).create(1)
        invite = await s.scalar(select(AdminInvite))
        now = datetime.now(timezone.utc)
        if state == 'expired':
            invite.expires_at = now - timedelta(seconds=1)
        elif state == 'revoked':
            invite.revoked_at = now
        else:
            invite.used_at = now
        await s.flush()
        with pytest.raises(AppError):
            await InviteService(s).accept(raw, u.id)
        assert await s.scalar(select(func.count(Admin.id))) == 0
