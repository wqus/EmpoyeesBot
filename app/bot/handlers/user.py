from app.core.exceptions import AppError
from aiogram.exceptions import TelegramAPIError
import random
import secrets
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from app.bot.states.registration import Registration, LessonTest
from app.bot.keyboards.common import menu, owner_menu, studios, lessons
from app.database.models import MediaType
from app.repositories.core import UserRepository, StudioRepository, MaterialRepository
from app.services.core import RegistrationService, LearningService, LessonTestService, ExamService, ResultService
from app.services.admin import AccessService, InviteService
from app.core.config import settings
from app.utils.text import escape_html, text_chunks
from app.utils.lesson_ui import clean_lesson_title, normalize_lesson_text, split_number_buttons
from app.bot.middlewares.state_lock import UserFlowStateLockMiddleware
router = Router()
router.message.middleware(UserFlowStateLockMiddleware())
router.callback_query.middleware(UserFlowStateLockMiddleware())

TELEGRAM_TEXT_LIMIT = 3900

async def send_text_chunks(message, text: str, *, parse_mode=None):
    text = text or ''
    if not text:
        return
    for chunk in text_chunks(text, TELEGRAM_TEXT_LIMIT, html_mode=parse_mode == 'HTML'):
        await message.answer(chunk, parse_mode=parse_mode)


async def active_user(event, session):
    u = await UserRepository(session).by_tg(event.from_user.id)
    if not u:
        await event.answer('Сначала зарегистрируйтесь: /start')
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
    # The owner is the bootstrap identity of the system. It must be possible to
    # administer an empty database before any studios or employee accounts exist.
    if m.from_user.id == settings.owner_telegram_id:
        from app.bot.handlers.admin.panel import admin_panel_keyboard, cancel_keyboard
        current = await state.get_state()
        if current:
            return await m.answer(
                'Сначала завершите текущее действие или отмените его.',
                reply_markup=cancel_keyboard(),
            )
        # Telegram allows only one reply_markup per message, so first install the
        # persistent reply keyboard and then send the inline management panel.
        await m.answer(
            'Меню владельца доступно по кнопке ниже.',
            reply_markup=owner_menu(),
        )
        return await m.answer(
            '<b>Панель владельца</b>\n\nУправление обучением сотрудников.',
            parse_mode='HTML',
            reply_markup=admin_panel_keyboard(owner=True),
        )

    u = await UserRepository(session).by_tg(m.from_user.id)
    parts = (m.text or '').split(maxsplit=1)
    token = parts[1][6:] if len(parts) > 1 and parts[1].startswith('admin_') else None
    if u:
        await state.clear()
        if token:
            try:
                await InviteService(session).accept(token, u.id)
            except AppError as e:
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
    if not m.text or not 2 <= len(m.text.strip()) <= 255:
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
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    if d.get('token'):
        try:
            await InviteService(session).accept(d['token'], u.id)
        except AppError as e:
            await c.message.answer(f'Регистрация завершена, но invite не принят: {escape_html(str(e))}', parse_mode='HTML')
    await state.clear()
    await c.answer()
    await c.message.answer('Готово.', reply_markup=menu(await AccessService(session).admin(c.from_user.id)))

@router.message(F.text.in_({'Обучение', '📚 Обучение'}))
async def learning(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    await m.answer('Уроки', reply_markup=lessons(await LearningService(session).list(u.id)))

@router.callback_query(F.data.regexp('^lesson:\\d+$'))
async def lesson(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    try:
        l = await LearningService(session).lesson(u.id, int(c.data.split(':')[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    title = clean_lesson_title(l.title, l.position)
    header = f'<b>Урок {l.position}</b>\n<b>{escape_html(title)}</b>'
    if l.description:
        header += f'\n\n{escape_html(normalize_lesson_text(l.description))}'
    await c.message.answer(header, parse_mode='HTML')
    for x in sorted(l.media, key=lambda z: z.position):
        if x.media_type == MediaType.TEXT:
            text = normalize_lesson_text(x.content)
            if text:
                await send_text_chunks(c.message, text)
        elif x.media_type in {MediaType.PHOTO, MediaType.VIDEO, MediaType.DOCUMENT}:
            try:
                caption = normalize_lesson_text(x.content)[:1000] or None
                if x.media_type == MediaType.PHOTO:
                    await c.message.answer_photo(x.telegram_file_id, caption=caption)
                elif x.media_type == MediaType.VIDEO:
                    await c.message.answer_video(x.telegram_file_id, caption=caption)
                else:
                    await c.message.answer_document(x.telegram_file_id, caption=caption)
            except TelegramAPIError:
                await c.message.answer('Один из файлов урока сейчас недоступен. Сообщите администратору.')
    await c.message.answer(
        'Когда будете готовы, переходите к короткому тесту по этому уроку.',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Перейти к тесту', callback_data=f'test:start:{l.id}')]]),
    )

@router.callback_query(F.data.regexp(r'^test:start:\d+$'))
async def test_start(c: CallbackQuery, state: FSMContext, session):
    if await state.get_state() == LessonTest.answering.state:
        return await c.answer('Сначала завершите текущий тест или отмените его.', show_alert=True)
    u = await active_user(c, session)
    if not u:
        return
    lid = int(c.data.rsplit(':', 1)[1])
    try:
        await LearningService(session).lesson(u.id, lid)
        qs = await LessonTestService(session).questions(lid)
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    snap = [{'id': q.id, 'text': q.text, 'options': [{'id': o.id, 'text': o.text} for o in q.options]} for q in qs]
    await state.set_state(LessonTest.answering)
    await state.set_data({'lesson_id': lid, 'index': 0, 'questions': snap, 'answers': [], 'test_id': secrets.token_hex(4), 'revision': LessonTestService.revision(qs)})
    await c.answer()
    await send_test_question(c.message, await state.get_data())

async def send_test_question(message, data):
    q = data['questions'][data['index']]
    options_text = '\n'.join(f"{i}. {o['text']}" for i, o in enumerate(q['options'], 1))
    rows = []
    for row in split_number_buttons(q['options']):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"test:answer:{data['test_id']}:{q['id']}:{item['id']}") for label, item in row])
    rows.append([InlineKeyboardButton(text='Отменить тест', callback_data='test:cancel')])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        f"Вопрос {data['index'] + 1}/{len(data['questions'])}\n\n{q['text']}\n\nВарианты ответа:\n{options_text}\n\nВыберите номер ответа:",
        reply_markup=kb,
    )

@router.callback_query(LessonTest.answering, F.data.regexp(r'^test:answer:[0-9a-f]{8}:\d+:\d+$'))
async def test_answer(c: CallbackQuery, state: FSMContext, session):
    u = await active_user(c, session)
    if not u:
        return
    qid, oid = map(int, c.data.split(':')[-2:])
    d = await state.get_data()
    if len(c.data.split(':')) != 5 or c.data.split(':')[2] != d.get('test_id'):
        return await c.answer('Эта кнопка от предыдущей попытки.', show_alert=True)
    if d['questions'][d['index']]['id'] != qid:
        return await c.answer('Этот вопрос уже обработан.', show_alert=True)
    if not any(o['id'] == oid for o in d['questions'][d['index']]['options']):
        return await c.answer('Некорректный вариант ответа.', show_alert=True)
    d['answers'].append((qid, oid))
    d['index'] += 1
    await state.set_data(d)
    await c.answer()
    if d['index'] < len(d['questions']):
        return await send_test_question(c.message, d)
    try:
        correct, total, passed = await LessonTestService(session).finish(u.id, d['lesson_id'], d['answers'], expected_revision=d.get('revision'))
    except AppError as e:
        await state.clear()
        return await c.message.answer(f'Тест остановлен из-за изменения настроек: {escape_html(str(e))}. Запустите его заново.', parse_mode='HTML')
    await state.clear()
    required = LessonTestService.required(total)
    learning_service = LearningService(session)
    current_lesson = await learning_service.lesson(u.id, d['lesson_id'])
    markup = None
    if passed:
        progress = await learning_service.list(u.id)
        next_progress = next((p for p in progress if p.status.value == 'available'), None)
        text = f"Тест пройден.\nРезультат: {correct}/{total}.\n\nВы прошли уровень {current_lesson.position}."
        if next_progress:
            next_title = clean_lesson_title(next_progress.lesson.title, next_progress.lesson.position)
            text += f"\nТеперь вам доступен урок {next_progress.lesson.position}: {next_title}."
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'Открыть урок {next_progress.lesson.position}', callback_data=f'lesson:{next_progress.lesson_id}')]])
        else:
            text += "\nВсе уроки пройдены. Теперь вам доступен итоговый экзамен."
    else:
        text = f"Тест пока не пройден.\nРезультат: {correct}/{total}. Нужно минимум {required}/{total}.\n\nПовторите материал и попробуйте ещё раз — количество попыток не ограничено."
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пройти тест ещё раз', callback_data=f"test:start:{d['lesson_id']}")]])
    await c.message.answer(text, reply_markup=markup)

@router.callback_query(LessonTest.answering, F.data == 'test:cancel')
async def test_cancel(c: CallbackQuery, state: FSMContext, session):
    u = await active_user(c, session)
    if not u:
        return
    await state.clear()
    await c.answer('Тест отменён')
    await c.message.answer('Тест отменён. Вы можете начать его заново.', reply_markup=lessons(await LearningService(session).list(u.id)))


@router.message(F.text == 'Материалы')
async def materials(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    cats = await MaterialRepository(session).categories()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.name, callback_data=f'mat:cat:{x.id}')] for x in cats])
    await m.answer('Материалы' if cats else 'Материалы пока не добавлены.', reply_markup=kb if cats else None)

@router.callback_query(F.data.regexp(r'^mat:cat:\d+$'))
async def material_category(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    items = await MaterialRepository(session).materials(int(c.data.rsplit(':', 1)[1]))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.title, callback_data=f'mat:item:{x.id}')] for x in items])
    await c.answer()
    await c.message.answer('Выберите материал:' if items else 'В категории пока нет материалов.', reply_markup=kb if items else None)

@router.callback_query(F.data.regexp(r'^mat:item:\d+$'))
async def material_item(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    item = await MaterialRepository(session).material(int(c.data.rsplit(':', 1)[1]))
    if not item:
        return await c.answer('Материал недоступен.', show_alert=True)
    await c.answer()
    await c.message.answer(f'<b>{escape_html(item.title)}</b>', parse_mode='HTML')
    await send_text_chunks(c.message, item.content or '')
    for x in item.media:
        try:
            if x.media_type == MediaType.PHOTO:
                await c.message.answer_photo(x.telegram_file_id)
            elif x.media_type == MediaType.VIDEO:
                await c.message.answer_video(x.telegram_file_id)
            elif x.media_type == MediaType.DOCUMENT:
                await c.message.answer_document(x.telegram_file_id)
        except TelegramAPIError:
            await c.message.answer('Одно из вложений сейчас недоступно. Сообщите администратору.')

async def send_exam_question(message, service, u, a):
    slot = await service.current(u, a)
    if not slot:
        return False
    opts = list(slot.question.options)
    random.shuffle(opts)
    options_text = '\n'.join(f'{i}. {o.text}' for i, o in enumerate(opts, 1))
    rows = []
    for row in split_number_buttons(opts):
        rows.append([InlineKeyboardButton(text=label, callback_data=f'exam:answer:{a}:{slot.question_id}:{item.id}') for label, item in row])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        f'Вопрос {slot.position}/30\n\n{slot.question.text}\n\nВарианты ответа:\n{options_text}\n\nВыберите номер ответа:',
        reply_markup=kb,
    )
    return True

@router.message(F.text.in_({'Экзамен', '📝 Экзамен'}))
async def exam(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    service = ExamService(session)
    try:
        a = await service.start(u.id)
    except AppError as e:
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
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    await send_exam_question(c.message, service, u.id, a.id)

@router.callback_query(F.data.regexp(r'^exam:answer:\d+:\d+:\d+$'))
async def exam_answer(c: CallbackQuery, session):
    u = await active_user(c, session)
    if not u:
        return
    a, q, o = map(int, c.data.split(':')[-3:])
    service = ExamService(session)
    try:
        await service.answer(u.id, a, q, o)
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer()
    if await send_exam_question(c.message, service, u.id, a):
        return
    att = await service.finish(u.id, a)
    kb = None if att.passed else InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Пройти ещё раз', callback_data='exam:retry')]])
    await c.message.answer(f"{('Экзамен пройден' if att.passed else 'Экзамен не пройден')}\nРезультат: {att.correct_count}/{att.total_count}", reply_markup=kb)

@router.message(F.text.in_({'Мой результат', '📊 Мой результат'}))
async def results(m: Message, session):
    u = await active_user(m, session)
    if not u:
        return
    progress, exams, last, weak = await ResultService(session).summary(u.id)
    passed = sum((p.status.value == 'passed' for p in progress))
    exam_text = 'не проходил' if not last else f"{last.correct_count}/{last.total_count} — {('пройден' if last.passed else 'не пройден')}"
    weak_text = ', '.join((f'{k} ({v})' for k, v in weak.most_common())) or 'нет'
    await m.answer(f'<b>Мой результат</b>\n\nУроки: {passed}/{len(progress)}\nПопыток экзамена: {len(exams)}\nПоследний экзамен: {escape_html(exam_text)}\nСлабые темы: {escape_html(weak_text)}', parse_mode='HTML')


@router.callback_query()
async def stale_user_callback(c: CallbackQuery):
    await c.answer('Эта кнопка устарела или недоступна. Откройте раздел заново.', show_alert=True)
