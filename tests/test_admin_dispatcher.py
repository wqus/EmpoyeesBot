"""Execute admin editing routes, not just their service methods or source text."""
from sqlalchemy import select
from app.database.models import (
    Admin, AdminInvite, ExamQuestion, Lesson, LessonMedia, LessonQuestion,
    MaterialCategory, Material, MediaType, Studio,
)
from app.services.admin_crud import AdminCrudService
from tests.test_dispatcher_e2e import bot_app
from tests.test_runtime_audit import employee


async def callback(bot, value):
    calls = await bot.send(tg=1, callback=value)
    assert calls, value
    assert 'Не удалось выполнить действие' not in str(calls), value
    assert 'Эта кнопка устарела' not in str(calls), value
    return calls


async def form(bot, value, text=None, **kwargs):
    await callback(bot, value)
    assert await bot.state(1).get_state() is not None, value
    calls = await bot.send(tg=1, text=text, **kwargs)
    assert 'Не удалось выполнить действие' not in str(calls), value
    assert await bot.state(1).get_state() is None, (value, calls)


async def test_lesson_editing_and_media_routes(bot_app, db_factory):
    b = bot_app
    async with db_factory() as s:
        a = AdminCrudService(s)
        first = await a.create_lesson('First')
        second = await a.create_lesson('Second')
        lid, other = first.id, second.id
        block = await a.add_lesson_text(lid, 'Initial body')
        text_id = block.id
        q = await a.add_lesson_question(lid, 'Q', ['A', 'B', 'C'], 0)
        qid = q.id
        await s.commit()
    for route in ['admin:lessons', f'admin:lesson:{lid}', f'admin:lesson:content:{lid}', f'admin:lesson:content:item:{lid}:{text_id}', f'admin:lesson:questions:{lid}', f'admin:lesson:q:item:{lid}:{qid}', f'admin:lesson:q:options:{lid}:{qid}']:
        await callback(b, route)
    await form(b, f'admin:lesson:rename:{lid}', 'Renamed lesson')
    await form(b, f'admin:lesson:content:edit:{lid}:{text_id}', 'Updated body')
    for typ, payload in [
        ('photo', [{'file_id':'photo', 'file_unique_id':'p', 'width':10, 'height':10}]),
        ('video', {'file_id':'video', 'file_unique_id':'v', 'width':10, 'height':10, 'duration':1}),
        ('document', {'file_id':'doc', 'file_unique_id':'d'}),
    ]:
        await form(b, f'admin:lesson:media:{lid}', **{typ:payload}, caption='Caption')
    async with db_factory() as s:
        media = list((await s.scalars(select(LessonMedia).where(LessonMedia.lesson_id == lid, LessonMedia.media_type != MediaType.TEXT))).all())
        mids = [x.id for x in media]
        assert len(media) == 3
    for mid in mids:
        await callback(b, f'admin:lesson:content:item:{lid}:{mid}')
    await form(b, f'admin:lesson:content:caption:{lid}:{mids[0]}', 'New caption')
    await form(b, f'admin:lesson:content:replace:{lid}:{mids[0]}', document={'file_id':'replacement', 'file_unique_id':'r'})
    await form(b, f'admin:lesson:q:edittext:{lid}:{qid}', 'New question')
    await form(b, f'admin:lesson:q:editopts:{lid}:{qid}', '+A\nB\nC')
    async with db_factory() as s:
        q = await AdminCrudService(s).lesson_question(qid)
        oids = [o.id for o in q.options]
    await callback(b, f'admin:lesson:q:opt:{lid}:{qid}:{oids[1]}')
    await form(b, f'admin:lesson:q:opt:edit:{lid}:{qid}:{oids[1]}', 'Changed option')
    await callback(b, f'admin:lesson:q:opt:correct:{lid}:{qid}:{oids[1]}')
    await callback(b, f'd:admin:lesson:q:opt:delete:{lid}:{qid}:{oids[0]}')
    await callback(b, 'd:cancel')
    await callback(b, f'admin:lesson:q:opt:delete:{lid}:{qid}:{oids[0]}')
    await callback(b, f'admin:lesson:preview:{lid}')
    await callback(b, f'admin:lesson:move:{other}:-1')
    await callback(b, f'admin:lesson:toggle:{lid}')
    async with db_factory() as s:
        item = await AdminCrudService(s).lesson(lid)
        assert item.title == 'Renamed lesson' and item.is_active
        assert item.questions[0].options[0].text == 'Changed option'
        assert item.media[1].telegram_file_id == 'replacement'
    await callback(b, f'admin:lesson:toggle:{lid}')
    await callback(b, f'admin:lesson:q:toggle:{lid}:{qid}')
    await callback(b, f'admin:lesson:q:delete:{lid}:{qid}')
    await callback(b, f'admin:lesson:content:delete:{lid}:{mids[0]}')
    await callback(b, f'admin:lesson:delete:{lid}')
    async with db_factory() as s:
        assert await s.get(Lesson, lid) is None


async def test_exam_material_studio_and_reporting_routes(bot_app, db_factory):
    b = bot_app
    async with db_factory() as s:
        a = AdminCrudService(s)
        u = await employee(s)
        uid, sid = u.id, u.studio_id
        first = await a.create_lesson('Topic one')
        second = await a.create_lesson('Topic two')
        lid = second.id
        q = await a.create_exam_question(first.id, 'Question', ['A', 'B', 'C'], 0)
        qid = q.id
        cat = await a.create_category('Category')
        cid = cat.id
        mat = await a.create_material(cid, 'First', 'Body')
        mid = mat.id
        mat2 = await a.create_material(cid, 'Second', 'Body')
        mid2 = mat2.id
        await s.commit()
    for route in [f'admin:studio:{sid}', 'admin:studios', 'admin:users', 'admin:users:p:99', f'admin:user:{uid}', f'admin:user:results:{uid}', 'admin:exam:history', 'admin:exam:history:p:1', 'admin:analytics', 'owner:audit:0', 'owner:audit:1', 'admin:exam', 'admin:exam:p:99', f'admin:exam:q:{qid}', f'admin:exam:options:{qid}']:
        await callback(b, route)
    await form(b, f'admin:studio:rename:{sid}', 'Updated studio')
    await callback(b, f'admin:studio:toggle:{sid}')
    await callback(b, f'admin:user:toggle:{uid}')
    await form(b, f'admin:exam:edittext:{qid}', 'Updated exam')
    await form(b, f'admin:exam:editopts:{qid}', '+A\nB\nC')
    await callback(b, f'admin:exam:edittopic:{qid}')
    await callback(b, f'admin:exam:settopic:{qid}:{lid}')
    async with db_factory() as s:
        q = await AdminCrudService(s).exam_question(qid)
        oids = [o.id for o in q.options]
    await callback(b, f'admin:exam:opt:{qid}:{oids[1]}')
    await form(b, f'admin:exam:opt:edit:{qid}:{oids[1]}', 'Updated option')
    await callback(b, f'admin:exam:opt:correct:{qid}:{oids[1]}')
    await callback(b, f'admin:exam:opt:delete:{qid}:{oids[0]}')
    await callback(b, f'admin:exam:toggle:{qid}')
    async with db_factory() as s:
        q = await s.get(ExamQuestion, qid)
        assert q.text == 'Updated exam' and q.lesson_id == lid and q.is_active
    await callback(b, f'admin:exam:toggle:{qid}')
    await callback(b, f'admin:exam:delete:{qid}')
    for route in ['admin:materials', f'admin:mat:cat:{cid}', f'admin:mat:item:{mid}']:
        await callback(b, route)
    await form(b, f'admin:mat:cat:rename:{cid}', 'New category')
    await form(b, f'admin:mat:edit:title:{mid}', 'New title')
    await form(b, f'admin:mat:edit:content:{mid}', 'New body')
    await form(b, f'admin:mat:media:{mid}', document={'file_id':'document', 'file_unique_id':'d'})
    await callback(b, f'admin:mat:media:list:{mid}')
    async with db_factory() as s:
        item = await AdminCrudService(s).material(mid)
        fid = item.media[0].id
        assert item.title == 'New title' and item.content == 'New body'
    await callback(b, f'admin:mat:media:delete:{mid}:{fid}')
    await callback(b, f'admin:mat:move:{mid2}:-1')
    await callback(b, f'admin:mat:toggle:{mid}')
    await callback(b, f'admin:mat:toggle:{mid}')
    await callback(b, f'admin:mat:delete:{mid}')
    await callback(b, f'admin:mat:delete:{mid2}')
    await callback(b, f'admin:mat:cat:delete:{cid}')
    async with db_factory() as s:
        assert await s.get(MaterialCategory, cid) is None


async def test_owner_invite_revoke_and_admin_removal_routes(bot_app, db_factory):
    b = bot_app
    async with db_factory() as s:
        u = await employee(s)
        uid = u.id
        s.add(Admin(user_id=uid))
        await s.commit()
    for route in ['owner:admins', 'owner:admins:list', 'owner:invite:create', 'owner:invites:list']:
        await callback(b, route)
    async with db_factory() as s:
        iid = await s.scalar(select(AdminInvite.id))
    await callback(b, f'owner:invite:revoke:{iid}')
    await callback(b, f'owner:admin:remove:{uid}')
    async with db_factory() as s:
        assert (await s.get(AdminInvite, iid)).revoked_at is not None
        assert await s.scalar(select(Admin).where(Admin.user_id == uid)) is None
