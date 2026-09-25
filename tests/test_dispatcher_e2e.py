import asyncio
import pytest
from sqlalchemy import func, select

from app.database.models import (
    Admin, AdminAction, ExamAttempt, ExamQuestion, ExamAnswerOption, Lesson,
    LessonTestAttempt, Material, Studio, User,
)
from app.services.admin_crud import AdminCrudService
from app.services.core import LearningService
from tests.bot_harness import make_harness
from tests.test_runtime_audit import employee, lesson


@pytest.fixture
async def bot_app(db_factory, monkeypatch):
    import app.bot.middlewares.database as middleware
    monkeypatch.setattr(middleware, 'async_session_factory', db_factory)
    harness = make_harness()
    yield harness
    await harness.dp.storage.close()
    await harness.dp.fsm.events_isolation.close()
    await harness.bot.session.close()


async def test_full_course_registration_fail_retry_exam_history(bot_app, db_factory, monkeypatch):
    import app.seed_oasis as seed
    monkeypatch.setattr(seed, 'async_session_factory', db_factory)
    assert await seed.seed_oasis_course() is True
    assert await seed.seed_oasis_course() is False
    async with db_factory() as s:
        studio = await AdminCrudService(s).create_studio('Main Studio')
        studio_id = studio.id
        await s.commit()
    b = bot_app
    await b.send(text='/start')
    assert await b.state(1001).get_state() == 'Registration:name'
    await b.send(text='Test Employee')
    await b.send(callback=f'reg:{studio_id}')
    assert await b.state(1001).get_state() is None
    calls = await b.send(text='Экзамен')
    assert 'Сначала пройдите' in str(calls)
    await b.send(text='Обучение')
    async with db_factory() as s:
        ids = list((await s.scalars(select(Lesson.id).order_by(Lesson.position))).all())
    for index, lid in enumerate(ids):
        for score in ([3, 4] if index == 0 else [5]):
            await b.send(callback=f'lesson:{lid}')
            await b.send(callback=f'test:start:{lid}')
            snapshot = await b.state(1001).get_data()
            for qi, q in enumerate(snapshot['questions']):
                from app.database.models import LessonAnswerOption
                async with db_factory() as s:
                    oid = await s.scalar(select(LessonAnswerOption.id).where(
                        LessonAnswerOption.question_id == q['id'],
                        LessonAnswerOption.is_correct.is_(qi < score)))
                callback = next(v for v in b.callbacks('test:answer:') if v.endswith(f':{oid}'))
                await b.send(callback=callback)
            assert await b.state(1001).get_state() is None
    # Two complete exam attempts exercise the 26/30 and 27/30 boundary via Update routing.
    for score in (26, 27):
        await b.send(text='Экзамен')
        for qi in range(30):
            callbacks = b.callbacks('exam:answer:')
            qid = int(callbacks[0].split(':')[-2])
            async with db_factory() as s:
                oid = await s.scalar(select(ExamAnswerOption.id).where(
                    ExamAnswerOption.question_id == qid, ExamAnswerOption.is_correct.is_(qi < score)))
            await b.send(callback=next(v for v in callbacks if v.endswith(f':{oid}')))
        async with db_factory() as s:
            attempt = await s.scalar(select(ExamAttempt).order_by(ExamAttempt.id.desc()))
            assert (attempt.correct_count, attempt.passed) == (score, score >= 27)
    calls = await b.send(text='Мой результат')
    assert '10/10' in str(calls) and 'Попыток экзамена: 2' in str(calls)
    async with db_factory() as s:
        assert await s.scalar(select(func.count(LessonTestAttempt.id))) == 11
        assert await s.scalar(select(func.count(ExamAttempt.id))) == 2


async def test_admin_can_use_training_callbacks(bot_app, db_factory):
    async with db_factory() as s:
        u = await employee(s)
        s.add(Admin(user_id=u.id))
        item = await lesson(s)
        lid = item.id
        await s.commit()
    await bot_app.send(text='Обучение')
    calls = await bot_app.send(callback=f'lesson:{lid}')
    assert 'Theory' in str(calls)
    await bot_app.send(callback=f'test:start:{lid}')
    assert await bot_app.state(1001).get_state() == 'LessonTest:answering'


async def test_fsm_message_and_old_answer_validation(bot_app, db_factory):
    async with db_factory() as s:
        await employee(s)
        item = await lesson(s)
        lid = item.id
        await s.commit()
    b = bot_app
    await b.send(callback=f'test:start:{lid}')
    state = await b.state(1001).get_data()
    qid = state['questions'][0]['id']
    invalid = f"test:answer:{state['test_id']}:{qid}:999999"
    await b.send(callback=invalid)
    await b.send(text='Мой результат')
    assert (await b.state(1001).get_data())['index'] == 0
    old = b.callbacks('test:answer:')[0]
    await b.send(callback='test:cancel')
    await b.send(callback=f'test:start:{lid}')
    await b.send(callback=old)
    assert (await b.state(1001).get_data())['index'] == 0
    current = b.callbacks('test:answer:')[0]
    await asyncio.gather(b.send(callback=current), b.send(callback=current))
    assert (await b.state(1001).get_data())['index'] == 1


async def test_registration_state_message_and_invalid_studio(bot_app, db_factory):
    async with db_factory() as s:
        studio = await AdminCrudService(s).create_studio('Available')
        sid = studio.id
        await s.commit()
    b = bot_app
    await b.send(text='/start')
    await b.send(text='x' * 256)
    assert await b.state(1001).get_state() == 'Registration:name'
    await b.send(text='Test Employee')
    await b.send(text='Мой результат')
    assert await b.state(1001).get_state() == 'Registration:studio'
    async with db_factory() as s:
        await AdminCrudService(s).toggle_studio(sid)
        await s.commit()
    await b.send(callback=f'reg:{sid}')
    assert await b.state(1001).get_state() == 'Registration:studio'


async def test_owner_bootstrap_admin_forms_and_audit(bot_app, db_factory):
    b = bot_app
    calls = await b.send(tg=1, text='/start')
    assert 'Панель владельца' in str(calls)
    await b.send(tg=1, callback='admin:studio:create')
    await b.send(tg=1, text='Обучение')
    assert await b.state(1).get_state() == 'StudioAdminState:create'
    await b.send(tg=1, document={'file_id': 'file', 'file_unique_id': 'unique'})
    assert await b.state(1).get_state() == 'StudioAdminState:create'
    await b.send(tg=1, text='Studio via UI')
    assert await b.state(1).get_state() is None
    await b.send(tg=1, callback='admin:lesson:create')
    await b.send(tg=1, text='Lesson via UI')
    async with db_factory() as s:
        lid = await s.scalar(select(Lesson.id))
    await b.send(tg=1, callback=f'admin:lesson:text:{lid}')
    await b.send(tg=1, text='Theory via UI')
    await b.send(tg=1, callback=f'admin:lesson:q:{lid}')
    await b.send(tg=1, text='Question via UI')
    await b.send(tg=1, text='+Correct\nIncorrect')
    await b.send(tg=1, callback=f'admin:lesson:toggle:{lid}')
    async with db_factory() as s:
        assert (await s.get(Lesson, lid)).is_active
        actions = list((await s.scalars(select(AdminAction))).all())
        assert len(actions) == 5
        assert {a.actor_telegram_id for a in actions} == {1}
    await b.send(tg=1, callback='admin:exam:create')
    await b.send(tg=1, callback=f'admin:exam:lesson:{lid}')
    await b.send(tg=1, text='Exam via UI')
    await b.send(tg=1, text='+Correct\nIncorrect')
    assert await b.state(1).get_state() is None
    await b.send(tg=1, callback='admin:mat:cat:create')
    await b.send(tg=1, text='Category UI')
    from app.database.models import MaterialCategory
    async with db_factory() as s:
        cid = await s.scalar(select(MaterialCategory.id))
    await b.send(tg=1, callback=f'admin:mat:create:{cid}')
    await b.send(tg=1, text='Material UI')
    await b.send(tg=1, text='Body')
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Material.id))) == 1


async def test_rbac_and_revoked_admin_cancel(bot_app, db_factory):
    async with db_factory() as s:
        u = await employee(s)
        uid = u.id
        await s.commit()
    b = bot_app
    await b.send(callback='admin:studio:create')
    await b.send(callback='owner:invite:create')
    assert await b.state(1001).get_state() is None
    async with db_factory() as s:
        s.add(Admin(user_id=uid))
        await s.commit()
    await b.send(callback='owner:invite:create')
    await b.send(callback='admin:studio:create')
    async with db_factory() as s:
        u = await s.get(User, uid)
        u.is_active = False
        await s.commit()
    await b.send(text='Forbidden Studio')
    await b.send(callback='fsm:cancel')
    assert await b.state(1001).get_state() is None
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Studio.id))) == 1


async def test_transport_failure_rolls_back_and_restores_state(bot_app, db_factory):
    b = bot_app
    await b.send(tg=1, callback='admin:studio:create')
    b.recorder.fail_next = True
    await b.send(tg=1, text='Uncommitted')
    assert await b.state(1).get_state() == 'StudioAdminState:create'
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Studio.id))) == 0
        assert await s.scalar(select(func.count(AdminAction.id))) == 0
    await b.send(tg=1, text='Committed')
    assert await b.state(1).get_state() is None


@pytest.mark.parametrize('callback', ['test:start:garbage', 'exam:answer:1:bad:3', 'lesson:999999999999999999', 'admin:lesson:99999999999999999', 'test:answer:bad'])
async def test_malformed_callback_is_answered(bot_app, callback):
    calls = await bot_app.send(callback=callback)
    assert any(type(call).__name__ == 'AnswerCallbackQuery' for call in calls)


async def test_repeated_mutating_button_and_update_replay(bot_app, db_factory):
    async with db_factory() as s:
        studio = await AdminCrudService(s).create_studio('Studio')
        sid = studio.id
        await s.commit()
    b = bot_app
    for _ in range(2):
        await b.send(tg=1, callback=f'admin:studio:toggle:{sid}', message_id=500)
    async with db_factory() as s:
        assert (await s.get(Studio, sid)).is_active is False
        assert await s.scalar(select(func.count(AdminAction.id))) == 1
    # Same Telegram update_id cannot execute a second mutation, even with altered payload.
    b.counter -= 1
    await b.send(tg=1, callback=f'admin:studio:toggle:{sid}', message_id=501)
    async with db_factory() as s:
        assert (await s.get(Studio, sid)).is_active is False
    await b.send(tg=1, callback=f'admin:studio:toggle:{sid}', message_id=502)
    async with db_factory() as s:
        assert (await s.get(Studio, sid)).is_active is True


async def test_all_admin_states_reject_wrong_input_and_cancel(bot_app):
    from app.bot.states.admin import StudioAdminState, LessonAdminState, ExamAdminState, MaterialAdminState
    b = bot_app
    for group in (StudioAdminState, LessonAdminState, ExamAdminState, MaterialAdminState):
        for current in group.__all_states__:
            await b.state(1).set_state(current)
            await b.state(1).set_data({'marker': 'preserve'})
            await b.send(tg=1, callback='admin:studios')
            assert await b.state(1).get_state() == current.state
            await b.send(tg=1, text='/start')
            assert await b.state(1).get_data() == {'marker': 'preserve'}
            await b.send(tg=1, callback='fsm:cancel')
            assert await b.state(1).get_state() is None
            assert await b.state(1).get_data() == {}


async def test_independent_users_and_restart_state(bot_app, db_factory):
    b = bot_app
    async with db_factory() as s:
        await AdminCrudService(s).create_studio('Studio')
        await s.commit()
    await asyncio.gather(b.send(tg=1001, text='/start'), b.send(tg=2002, text='/start'))
    await b.send(tg=1001, text='First Employee')
    assert await b.state(1001).get_state() == 'Registration:studio'
    assert await b.state(2002).get_state() == 'Registration:name'
    # A restart intentionally discards unfinished memory-backed forms.
    await b.dp.storage.close()
    b.dp.storage.storage.clear()
    calls = await b.send(tg=1001, callback='reg:1')
    assert 'устарела' in str(calls)
    await b.send(tg=1001, text='/start')
    assert await b.state(1001).get_state() == 'Registration:name'


async def test_commit_failure_rolls_back_business_data_and_fsm(bot_app, db_factory, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    b = bot_app
    await b.send(tg=1, callback='admin:studio:create')
    real_commit = AsyncSession.commit
    async def failed_commit(self):
        raise RuntimeError('Injected commit failure')
    monkeypatch.setattr(AsyncSession, 'commit', failed_commit)
    await b.send(tg=1, text='Lost write')
    monkeypatch.setattr(AsyncSession, 'commit', real_commit)
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Studio.id))) == 0
    assert await b.state(1).get_state() == 'StudioAdminState:create'
    await b.send(tg=1, text='Retry write')
    async with db_factory() as s:
        assert await s.scalar(select(func.count(Studio.id))) == 1


async def test_exam_creation_empty_bank_and_topic_cancel(bot_app, db_factory):
    b = bot_app
    calls = await b.send(tg=1, callback='admin:exam:create')
    assert 'Сначала создайте' in str(calls)
    assert await b.state(1).get_state() is None
    async with db_factory() as s:
        await AdminCrudService(s).create_lesson('Topic')
        await s.commit()
    await b.send(tg=1, callback='admin:exam:create')
    assert b.callbacks('fsm:cancel') == ['fsm:cancel']
    calls = await b.send(tg=1, text='Unexpected input')
    assert 'Выберите тему кнопкой' in str(calls)
    await b.send(tg=1, callback='fsm:cancel')
    assert await b.state(1).get_state() is None
