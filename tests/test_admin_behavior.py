import pytest
from sqlalchemy import select
from app.core.exceptions import AppError, ContentValidationError
from app.database.models import (
    Lesson, LessonAnswerOption, LessonMedia, LessonProgress, Material,
    MediaType, Studio, User,
)
from app.services.admin_crud import AdminCrudService
from app.services.core import LearningService, LessonTestService
from tests.test_runtime_audit import employee, lesson, pass_lesson


async def test_lesson_crud_media_questions_options_and_positions(session):
    a = AdminCrudService(session)
    first = await a.create_lesson('First')
    second = await a.create_lesson('Second')
    await a.move_lesson(second.id, -1)
    assert [x.id for x in await a.lessons()] == [second.id, first.id]
    await a.rename_lesson(first.id, 'Renamed')
    with pytest.raises(ContentValidationError):
        await a.toggle_lesson(first.id)
    text = await a.add_lesson_text(first.id, 'Body')
    tid = text.id
    photo = await a.add_lesson_media(first.id, MediaType.PHOTO, 'photo', 'Caption')
    pid = photo.id
    video = await a.add_lesson_media(first.id, MediaType.VIDEO, 'video')
    document = await a.add_lesson_media(first.id, MediaType.DOCUMENT, 'doc')
    await a.edit_lesson_media_text(first.id, tid, 'Updated')
    await a.edit_lesson_media_caption(first.id, pid, 'New caption')
    await a.replace_lesson_media(first.id, pid, MediaType.VIDEO, 'replacement')
    await a.delete_lesson_media(first.id, video.id)
    current = await a.lesson(first.id)
    assert [x.position for x in current.media] == [1, 2, 3]
    q = await a.add_lesson_question(first.id, 'Question', ['Yes', 'No', 'Maybe'], 0)
    qid = q.id
    q = await a.lesson_question(qid)
    oids = [o.id for o in q.options]
    await a.edit_lesson_question_text(first.id, qid, 'New question')
    await a.edit_lesson_option_text(first.id, qid, oids[1], 'Nope')
    with pytest.raises(AppError):
        await a.delete_lesson_option(first.id, qid, oids[0])
    await a.set_lesson_correct_option(first.id, qid, oids[1])
    await a.delete_lesson_option(first.id, qid, oids[0])
    q = await a.lesson_question(qid)
    assert [o.position for o in q.options] == [1, 2]
    await a.edit_lesson_question_options(first.id, qid, ['New yes', 'New no'], 0)
    await a.toggle_lesson_question(first.id, qid)
    assert await a.lesson_publication_errors(first.id)
    await a.toggle_lesson_question(first.id, qid)
    assert await a.lesson_publication_errors(first.id) == []
    await a.toggle_lesson(first.id)
    with pytest.raises(AppError):
        await a.add_lesson_text(first.id, 'Forbidden')
    await a.toggle_lesson(first.id)
    await a.delete_lesson_question(first.id, qid)
    await a.delete_lesson(first.id)
    assert len(await a.lessons()) == 1


async def test_material_crud_publication_and_media(session):
    a = AdminCrudService(session)
    cat = await a.create_category('Category')
    cid = cat.id
    await a.rename_category(cid, 'Renamed category')
    first = await a.create_material(cid, 'First', None)
    fid = first.id
    with pytest.raises(ContentValidationError):
        await a.toggle_material(fid)
    await a.edit_material_title(fid, 'Renamed')
    await a.edit_material_content(fid, 'Body')
    media = await a.add_material_media(fid, MediaType.DOCUMENT, 'document')
    mid = media.id
    await a.add_material_media(fid, MediaType.PHOTO, 'photo')
    await a.delete_material_media(fid, mid)
    assert [m.position for m in (await a.material(fid)).media] == [1]
    await a.toggle_material(fid)
    with pytest.raises(AppError):
        await a.delete_material(fid)
    with pytest.raises(AppError):
        await a.delete_category(cid)
    await a.toggle_material(fid)
    second = await a.create_material(cid, 'Second', 'Body')
    await a.move_material(second.id, -1)
    assert [m.id for m in await a.materials(cid)] == [second.id, fid]
    await a.delete_material(fid)
    await a.delete_material(second.id)
    await a.delete_category(cid)
    assert await a.categories() == []


async def test_exam_question_full_edit_cycle(session):
    a = AdminCrudService(session)
    first = await a.create_lesson('First')
    second = await a.create_lesson('Second')
    q = await a.create_exam_question(first.id, 'Question', ['Yes', 'No', 'Maybe'], 0)
    qid = q.id
    await a.edit_exam_text(qid, 'Changed')
    await a.change_exam_lesson(qid, second.id)
    q = await a.exam_question(qid)
    ids = [o.id for o in q.options]
    await a.edit_exam_option_text(qid, ids[1], 'Nope')
    await a.set_exam_correct_option(qid, ids[1])
    await a.delete_exam_option(qid, ids[0])
    await a.edit_exam_options(qid, ['A', 'B'], 1)
    await a.toggle_exam_question(qid)
    with pytest.raises(AppError):
        await a.edit_exam_text(qid, 'Forbidden')
    await a.toggle_exam_question(qid)
    await a.delete_exam_question(qid)
    assert await a.exam_question(qid) is None


async def test_history_protection_and_revision_check(session):
    u = await employee(session)
    item = await lesson(session)
    await LearningService(session).list(u.id)
    a = AdminCrudService(session)
    service = LessonTestService(session)
    qs = await service.questions(item.id)
    revision = service.revision(qs)
    answers = [(q.id, next(o.id for o in q.options if o.is_correct)) for q in qs]
    await a.toggle_lesson(item.id)
    await a.edit_lesson_question_text(item.id, qs[0].id, 'Changed in progress')
    await a.toggle_lesson(item.id)
    with pytest.raises(AppError):
        await service.finish(u.id, item.id, answers, expected_revision=revision)
    await pass_lesson(session, u, item)
    await a.toggle_lesson(item.id)
    with pytest.raises(AppError):
        await a.edit_lesson_question_text(item.id, qs[0].id, 'Changed after pass')
    with pytest.raises(AppError):
        await a.delete_lesson(item.id)
    _, progress, attempts, exams, weak = await a.user_results(u.id)
    assert len(attempts) == 1 and attempts[0].passed
    assert len(progress) == 1 and exams == [] and not weak
    assert (await a.dashboard())['passed_by_studio'].get(u.studio_id, 0) == 0


async def test_studio_and_owner_guards(session):
    u = await employee(session)
    a = AdminCrudService(session)
    with pytest.raises(AppError):
        await a.create_studio('studio 1001')
    with pytest.raises(AppError):
        await a.delete_studio(u.studio_id)
    spare = await a.create_studio('Spare')
    await a.rename_studio(spare.id, 'Renamed')
    await a.toggle_studio(spare.id)
    await a.delete_studio(spare.id)
    owner = User(telegram_id=1, full_name='Owner', studio_id=u.studio_id, is_active=True)
    session.add(owner)
    await session.flush()
    with pytest.raises(AppError):
        await a.toggle_user(owner.id)
    await a.toggle_user(u.id)
    with pytest.raises(AppError):
        await LearningService(session).list(u.id)


@pytest.mark.parametrize('method,args', [
    ('create_studio', ['x' * 256]), ('create_lesson', ['x' * 256]),
    ('create_category', ['x' * 256]), ('create_studio', [' ']),
])
async def test_oversized_or_empty_names_are_business_errors(session, method, args):
    with pytest.raises(AppError):
        await getattr(AdminCrudService(session), method)(*args)
