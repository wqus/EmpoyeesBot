import random
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from app.bot.states.registration import Registration, LessonTest
from app.bot.keyboards.common import menu, studios, lessons
from app.database.models import MediaType
from app.repositories.core import UserRepository, StudioRepository, MaterialRepository
from app.services.core import RegistrationService, LearningService, LessonTestService, ExamService, ResultService
from app.services.admin import AccessService, InviteService
from app.utils.text import escape_html
router = Router()

async def active_user(event, session):
    u = await UserRepository(session).by_tg(event.from_user.id)
    if not u:
        return None
    if not u.is_active:
        if isinstance(event, CallbackQuery):
            await event.answer('Ваш доступ отключён.', show_alert=True)
        else:
            await event.answer('⛔️ Ваш доступ к обучению отключён. Обратитесь к администратору.')
        return False
    return u

@router.message(CommandStart())
async def start(m: Message, state: FSMContext, session):
    u = await UserRepository(session).by_tg(m.from_user.id)
    parts = (m.text or '').split(maxsplit=1)
    token = parts[1][6:] if len(parts) > 1 and parts[1].startswith('admin_') else None
    if u:
        await state.clear()
        if token:
            try:
                await InviteService(session).accept(token, u.id)
            except Exception as e:
                await m.answer(f'Приглашение: {escape_html(str(e))}', parse_mode='HTML')
        if not u.is_active:
            return await m.answer('⛔️ Ваш доступ отключён. Обратитесь к администратору.')
        return await m.answer('Главное меню', reply_markup=menu(await AccessService(session).admin(m.from_user.id)))
    await state.clear()
    await state.update_data(token=token)
    await state.set_state(Registration.name)
    await m.answer('Введите ФИО:')

@router.message(Registration.name)
async def reg_name(m: Message, state: FSMContext, session):
    if not m.text or len(m.text.strip()) < 2:
        return await m.answer('Введите корректное ФИО текстом.')
    available = await StudioRepository(session).active()
    if not available:
        await state.clear()
        return await m.answer('Сейчас нет доступных студий. Обратитесь к администратору.')
    await state.update_data(name=m.text.strip())
    await state.set_state(Registration.studio)
    await m.answer('Выберите студию:', reply_markup=studios(available))

@router.callback_query(Registration.studio, F.data.regexp('^reg:\\d+$'))
async def reg_studio(c: CallbackQuery, state: FSMContext, session):
    d = await state.get_data()
    try:
        u = await RegistrationService(session).register(c.from_user.id, d['name'], int(c.data.split(':')[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    if d.get('token'):
        try:
            await InviteService(session).accept(d['token'], u.id)
        except Exception as e:
            await c.message.answer(f'Регистрация завершена, но invite не принят: {escape_html(str(e))}', parse_mode='HTML')
    await state.clear()
    await c.answer()
    await c.message.answer('Готово.', reply_markup=menu(await AccessService(session).admin(c.from_user.id)))

@router.message(F.text == '📚 Обучение')
async def learning(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    await m.answer('📚 Уроки', reply_markup=lessons(await LearningService(session).list(u.id)))

@router.callback_query(F.data.regexp('^lesson:\\d+$'))
async def lesson(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    try:
        l = await LearningService(session).lesson(u.id, int(c.data.split(':')[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    await c.message.answer(f'📚 <b>{escape_html(l.title)}</b>\n\n{escape_html(l.description)}', parse_mode='HTML')
    for x in l.media:
        if x.media_type == MediaType.TEXT:
            await c.message.answer(escape_html(x.content), parse_mode='HTML')
        elif x.media_type == MediaType.PHOTO:
            await c.message.answer_photo(x.telegram_file_id, caption=x.content)
        elif x.media_type == MediaType.VIDEO:
            await c.message.answer_video(x.telegram_file_id, caption=x.content)
        elif x.media_type == MediaType.DOCUMENT:
            await c.message.answer_document(x.telegram_file_id, caption=x.content)
    await c.message.answer('Тест:', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📝 Начать', callback_data=f'test:start:{l.id}')]]))

@router.callback_query(F.data.startswith('test:start:'))
async def test_start(c: CallbackQuery, state: FSMContext, session):
    u = await active_user(c, session)
    if not u:
        return
    lid = int(c.data.rsplit(':', 1)[1])
    try:
        await LearningService(session).lesson(u.id, lid)
        qs = await LessonTestService(session).questions(lid)
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    snap = [{'id': q.id, 'text': q.text, 'options': [{'id': o.id, 'text': o.text} for o in q.options]} for q in qs]
    await state.set_state(LessonTest.answering)
    await state.set_data({'lesson_id': lid, 'index': 0, 'questions': snap, 'answers': []})
    await c.answer()
    await send_test_question(c.message, await state.get_data())

async def send_test_question(message, data):
    q = data['questions'][data['index']]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=o['text'], callback_data=f"test:answer:{q['id']}:{o['id']}")] for o in q['options']])
    await message.answer(f"Вопрос {data['index'] + 1}/{len(data['questions'])}\n\n{q['text']}", reply_markup=kb)

@router.callback_query(LessonTest.answering, F.data.startswith('test:answer:'))
async def test_answer(c: CallbackQuery, state: FSMContext, session):
    u = await active_user(c, session)
    if not u:
        return
    qid, oid = map(int, c.data.split(':')[-2:])
    d = await state.get_data()
    if d['questions'][d['index']]['id'] != qid:
        return await c.answer('Этот вопрос уже обработан.', show_alert=True)
    d['answers'].append((qid, oid))
    d['index'] += 1
    await state.set_data(d)
    await c.answer()
    if d['index'] < len(d['questions']):
        return await send_test_question(c.message, d)
    try:
        correct, total, passed = await LessonTestService(session).finish(u.id, d['lesson_id'], d['answers'])
    except Exception as e:
        return await c.message.answer(f'Ошибка теста: {escape_html(str(e))}', parse_mode='HTML')
    await state.clear()
    required = LessonTestService.required(total)
    await c.message.answer(f"{('✅ Тест пройден' if passed else '❌ Тест не пройден')}\nРезультат: {correct}/{total}\nПроходной: {required}/{total}")

@router.message(F.text == '📖 Материалы')
async def materials(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    cats = await MaterialRepository(session).categories()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.name, callback_data=f'mat:cat:{x.id}')] for x in cats])
    await m.answer('📖 Материалы' if cats else 'Материалы пока не добавлены.', reply_markup=kb if cats else None)

@router.callback_query(F.data.startswith('mat:cat:'))
async def material_category(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    items = await MaterialRepository(session).materials(int(c.data.rsplit(':', 1)[1]))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.title, callback_data=f'mat:item:{x.id}')] for x in items])
    await c.answer()
    await c.message.answer('Выберите материал:' if items else 'В категории пока нет материалов.', reply_markup=kb if items else None)

@router.callback_query(F.data.startswith('mat:item:'))
async def material_item(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    item = await MaterialRepository(session).material(int(c.data.rsplit(':', 1)[1]))
    if not item:
        return await c.answer('Материал недоступен.', show_alert=True)
    await c.answer()
    await c.message.answer(f'📖 <b>{escape_html(item.title)}</b>\n\n{escape_html(item.content)}', parse_mode='HTML')
    for x in item.media:
        if x.media_type == MediaType.PHOTO:
            await c.message.answer_photo(x.telegram_file_id)
        elif x.media_type == MediaType.VIDEO:
            await c.message.answer_video(x.telegram_file_id)
        elif x.media_type == MediaType.DOCUMENT:
            await c.message.answer_document(x.telegram_file_id)

async def send_exam_question(message, service, u, a):
    slot = await service.current(u, a)
    if not slot:
        return False
    opts = list(slot.question.options)
    random.shuffle(opts)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=o.text, callback_data=f'exam:answer:{a}:{slot.question_id}:{o.id}')] for o in opts])
    await message.answer(f'🎓 Вопрос {slot.position}/30\n\n{slot.question.text}', reply_markup=kb)
    return True

@router.message(F.text == '📝 Экзамен')
async def exam(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    service = ExamService(session)
    try:
        a = await service.start(u.id)
    except Exception as e:
        return await m.answer(f'Экзамен недоступен: {escape_html(str(e))}', parse_mode='HTML')
    await send_exam_question(m, service, u.id, a.id)

@router.callback_query(F.data == 'exam:retry')
async def exam_retry(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    service = ExamService(session)
    try:
        a = await service.start(u.id)
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    await send_exam_question(c.message, service, u.id, a.id)

@router.callback_query(F.data.startswith('exam:answer:'))
async def exam_answer(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    a, q, o = map(int, c.data.split(':')[-3:])
    service = ExamService(session)
    try:
        await service.answer(u.id, a, q, o)
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    if await send_exam_question(c.message, service, u.id, a):
        return
    att = await service.finish(u.id, a)
    kb = None if att.passed else InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Пройти ещё раз', callback_data='exam:retry')]])
    await c.message.answer(f"{('🎉 Экзамен пройден!' if att.passed else '❌ Экзамен не пройден')}\nРезультат: {att.correct_count}/{att.total_count}", reply_markup=kb)
    from app.core.config import settings
    from app.repositories.core import AdminRepository
    _, _, _, weak = await ResultService(session).summary(u.id)
    weak_text = ', '.join((f'{k} ({v})' for k, v in weak.most_common())) or 'нет'
    report = f"📊 <b>Завершён экзамен</b>\nСотрудник: {escape_html(u.full_name)}\nСтудия: {escape_html(u.studio.name)}\nРезультат: {att.correct_count}/{att.total_count}\nСтатус: {('✅ пройден' if att.passed else '❌ не пройден')}\nСлабые темы: {escape_html(weak_text)}"
    recipients = {settings.owner_telegram_id}
    for admin in await AdminRepository(session).all():
        if admin.user.is_active:
            recipients.add(admin.user.telegram_id)
    for tg in recipients:
        try:
            await c.bot.send_message(tg, report, parse_mode='HTML')
        except Exception:
            pass

@router.message(F.text == '📊 Мой результат')
async def results(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    progress, exams, last, weak = await ResultService(session).summary(u.id)
    passed = sum((p.status.value == 'passed' for p in progress))
    exam_text = 'не проходил' if not last else f"{last.correct_count}/{last.total_count} — {('пройден' if last.passed else 'не пройден')}"
    weak_text = ', '.join((f'{k} ({v})' for k, v in weak.most_common())) or 'нет'
    await m.answer(f'📊 <b>Мой результат</b>\n\nУроки: {passed}/{len(progress)}\nПопыток экзамена: {len(exams)}\nПоследний экзамен: {escape_html(exam_text)}\nСлабые темы: {escape_html(weak_text)}', parse_mode='HTML')
