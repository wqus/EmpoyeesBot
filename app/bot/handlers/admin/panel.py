from app.core.exceptions import AppError
from aiogram.exceptions import TelegramAPIError
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.bot.filters.access import IsAdminOrOwner
from app.bot.states.admin import StudioAdminState, LessonAdminState, ExamAdminState, MaterialAdminState
from app.database.models import MediaType
from app.services.admin_crud import AdminCrudService
from app.utils.text import escape_html
from app.utils.lesson_ui import clean_lesson_title, normalize_lesson_text
from app.bot.middlewares.state_lock import StateLockMiddleware
router = Router()
router.message.filter(IsAdminOrOwner())
router.callback_query.filter(IsAdminOrOwner())
router.callback_query.middleware(StateLockMiddleware())

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return kb([[InlineKeyboardButton(text="Отменить и вернуться", callback_data="fsm:cancel")]])

PAGE_SIZE = 10

def pager(prefix: str, page: int, total: int):
    rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Предыдущая страница", callback_data=f"{prefix}:{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Следующая страница", callback_data=f"{prefix}:{page+1}"))
    if nav:
        rows.append(nav)
    return rows

def danger_callback(original: str) -> str:
    return f"d:{original}"


def audit_action_label(action: str) -> str:
    mapping = (
        ('admin:studio:create', 'Создание студии'),
        ('admin:studio:rename:', 'Переименование студии'),
        ('admin:studio:toggle:', 'Изменение статуса студии'),
        ('admin:studio:delete:', 'Удаление студии'),
        ('admin:user:toggle:', 'Изменение доступа сотрудника'),
        ('admin:lesson:create', 'Создание урока'),
        ('admin:lesson:delete:', 'Удаление урока'),
        ('admin:lesson:move:', 'Изменение порядка уроков'),
        ('admin:lesson:toggle:', 'Публикация или скрытие урока'),
        ('admin:exam:create', 'Создание вопроса экзамена'),
        ('admin:exam:delete:', 'Удаление вопроса экзамена'),
        ('admin:exam:toggle:', 'Изменение статуса вопроса экзамена'),
        ('admin:mat:cat:create', 'Создание категории материалов'),
        ('admin:mat:delete:', 'Удаление материала'),
        ('owner:invite:create', 'Создание приглашения администратора'),
        ('owner:admin:remove:', 'Удаление администратора'),
        ('owner:invite:revoke:', 'Отзыв приглашения администратора'),
    )
    for prefix, label in mapping:
        if action.startswith(prefix):
            return label
    if action.startswith('fsm:'):
        return 'Изменение данных через форму'
    return action
async def finish_state(message: Message, state: FSMContext, text: str, *, parse_mode=None):
    data = await state.get_data()
    return_cb = data.get('return_cb')
    await state.clear()
    markup = kb([[InlineKeyboardButton(text='Вернуться', callback_data=return_cb)]]) if return_cb else None
    await message.answer(text, parse_mode=parse_mode, reply_markup=markup)

@router.callback_query(F.data == "d:cancel")
async def danger_cancel(c: CallbackQuery):
    await c.answer("Отменено")
    await c.message.answer("Действие отменено.")

@router.callback_query(F.data.startswith("d:"))
async def confirm_danger(c: CallbackQuery):
    original = (c.data or "")[2:]
    allowed = (
        "admin:lesson:delete:", "admin:exam:delete:", "admin:mat:delete:",
        "admin:mat:cat:delete:", "admin:lesson:content:delete:",
        "admin:lesson:q:delete:", "admin:lesson:q:opt:delete:",
        "admin:exam:opt:delete:", "admin:mat:media:delete:",
        "owner:admin:remove:", "admin:studio:delete:",
    )
    if not original.startswith(allowed):
        return await c.answer("Недопустимое действие", show_alert=True)
    await c.answer()
    await c.message.answer(
        "Подтвердите действие. Отменить его после выполнения может быть невозможно.",
        reply_markup=kb([[
            InlineKeyboardButton(text="Подтвердить", callback_data=original),
            InlineKeyboardButton(text="Отмена", callback_data="d:cancel"),
        ]]),
    )

@router.callback_query(F.data == "fsm:cancel")
async def cancel_fsm(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    return_cb = data.get("return_cb")
    await state.clear()
    rows = [[InlineKeyboardButton(text="Вернуться", callback_data=return_cb)]] if return_cb else [[InlineKeyboardButton(text="Вернуться в админ-панель", callback_data="admin:studios")]]
    await c.answer("Действие отменено")
    await c.message.answer("Действие отменено. Несохранённые данные удалены.", reply_markup=kb(rows))

def admin_panel_keyboard(*, owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text='Студии', callback_data='admin:studios'), InlineKeyboardButton(text='Сотрудники', callback_data='admin:users')],
        [InlineKeyboardButton(text='Уроки', callback_data='admin:lessons'), InlineKeyboardButton(text='База экзамена', callback_data='admin:exam')],
        [InlineKeyboardButton(text='Материалы', callback_data='admin:materials'), InlineKeyboardButton(text='История экзаменов', callback_data='admin:exam:history')],
        [InlineKeyboardButton(text='Сводка обучения', callback_data='admin:analytics')],
    ]
    if owner:
        rows.append([InlineKeyboardButton(text='Администраторы', callback_data='owner:admins'), InlineKeyboardButton(text='История изменений', callback_data='owner:audit:0')])
    return kb(rows)

@router.message(F.text.in_({'Админ-панель', '⚙️ Админ-панель', '⚙️ Меню владельца'}))
async def menu(m: Message, state: FSMContext):
    from app.core.config import settings
    current = await state.get_state()
    if current:
        return await m.answer(
            'Сначала завершите текущее действие или отмените его.',
            reply_markup=cancel_keyboard(),
        )
    is_owner = m.from_user.id == settings.owner_telegram_id
    title = '<b>Панель владельца</b>' if is_owner else '<b>Админ-панель</b>'
    await m.answer(title, parse_mode='HTML', reply_markup=admin_panel_keyboard(owner=is_owner))

async def _show_users_page(c: CallbackQuery, session, page: int):
    service = AdminCrudService(session)
    total = await service.user_count()
    page = min(max(0, page), max(0, (total - 1) // PAGE_SIZE))
    chunk = await service.users(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    rows = [[InlineKeyboardButton(text=f"{('Активен - ' if x.is_active else 'Отключён - ')}{x.full_name}", callback_data=f'admin:user:{x.id}')] for x in chunk]
    rows += pager('admin:users:p', page, total)
    await c.answer()
    text = f'Сотрудники: {total}. Страница {page + 1}.' if total else 'Сотрудников пока нет.'
    await c.message.answer(text, reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data == 'admin:users')
async def users(c: CallbackQuery, session):
    await _show_users_page(c, session, 0)

@router.callback_query(F.data.regexp(r'^admin:users:p:\d+$'))
async def users_page(c: CallbackQuery, session):
    await _show_users_page(c, session, int(c.data.rsplit(':', 1)[1]))

@router.callback_query(F.data.regexp('^admin:user:\\d+$'))
async def user_card(c: CallbackQuery, session):
    u = await AdminCrudService(session).user(int(c.data.rsplit(':', 1)[1]))
    if not u:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f"<b>{escape_html(u.full_name)}</b>\nСтудия: {escape_html(u.studio.name)}\nСтатус: {('активен' if u.is_active else 'отключён')}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Результаты', callback_data=f'admin:user:results:{u.id}')], [InlineKeyboardButton(text='Отключить' if u.is_active else 'Включить', callback_data=f'admin:user:toggle:{u.id}')]]))

@router.callback_query(F.data.regexp('^admin:user:toggle:\\d+$'))
async def user_toggle(c: CallbackQuery, session):
    try:
        u = await AdminCrudService(session).toggle_user(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Статус изменён', show_alert=True)

@router.callback_query(F.data == 'admin:studios')
async def studios(c: CallbackQuery, session):
    items = await AdminCrudService(session).studios()
    rows = [[InlineKeyboardButton(text=f"{('Активен -' if x.is_active else 'Отключён -')} {x.name}", callback_data=f'admin:studio:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='Добавить студию', callback_data='admin:studio:create')])
    await c.answer()
    await c.message.answer('Студии', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:studio:create')
async def studio_create(c: CallbackQuery, state: FSMContext):
    await state.update_data(return_cb='admin:studios')
    await state.set_state(StudioAdminState.create)
    await c.answer()
    await c.message.answer('Название новой студии:', reply_markup=cancel_keyboard())

@router.message(StudioAdminState.create)
async def studio_create_name(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_studio(m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Студия «{escape_html(x.name)}» создана.', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:studio:\\d+$'))
async def studio_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).studio(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найдена', show_alert=True)
    await c.answer()
    await c.message.answer(f"<b>{escape_html(x.name)}</b>\nСтатус: {('активна' if x.is_active else 'скрыта')}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Переименовать', callback_data=f'admin:studio:rename:{x.id}')], [InlineKeyboardButton(text='Скрыть' if x.is_active else 'Включить', callback_data=f'admin:studio:toggle:{x.id}')], [InlineKeyboardButton(text='Удалить студию', callback_data=danger_callback(f'admin:studio:delete:{x.id}'))]]))

@router.callback_query(F.data.regexp('^admin:studio:rename:\\d+$'))
async def studio_rename(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(studio_id=sid, return_cb=f'admin:studio:{sid}')
    await state.set_state(StudioAdminState.rename)
    await c.answer()
    await c.message.answer('Новое название:', reply_markup=cancel_keyboard())

@router.message(StudioAdminState.rename)
async def studio_rename_name(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        x = await AdminCrudService(session).rename_studio(d['studio_id'], m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Переименовано: {escape_html(x.name)}', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:studio:toggle:\\d+$'))
async def studio_toggle(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).toggle_studio(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Статус изменён', show_alert=True)

@router.callback_query(F.data.regexp(r'^admin:studio:delete:\d+$'))
async def studio_delete(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_studio(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Студия удалена.', show_alert=True)
    await c.message.answer('Студия удалена.', reply_markup=kb([[InlineKeyboardButton(text='К списку студий', callback_data='admin:studios')]]))

@router.callback_query(F.data == 'admin:lessons')
async def lessons(c: CallbackQuery, session):
    items = await AdminCrudService(session).lessons()
    rows = [[InlineKeyboardButton(text=f"{('Активен -' if x.is_active else 'Отключён -')} {x.position}. {x.title}", callback_data=f'admin:lesson:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='Добавить урок', callback_data='admin:lesson:create')])
    await c.answer()
    await c.message.answer('Уроки', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:lesson:create')
async def lesson_create(c: CallbackQuery, state: FSMContext):
    await state.update_data(return_cb='admin:lessons')
    await state.set_state(LessonAdminState.create_title)
    await c.answer()
    await c.message.answer('Название урока:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.create_title)
async def lesson_create_title(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_lesson(m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Черновик урока #{x.id} создан.')

@router.callback_query(F.data.regexp('^admin:lesson:\\d+$'))
async def lesson_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).lesson(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найден', show_alert=True)
    service = AdminCrudService(session)
    errors = [] if x.is_active else await service.lesson_publication_errors(x.id)
    readiness = 'готов к публикации' if not errors else 'не готов: ' + '; '.join(errors[:4])
    await c.answer()
    await c.message.answer(f"<b>{escape_html(x.title)}</b>\nПозиция: {x.position}\nКонтент: {len(x.media)}\nВопросы: {len(x.questions)}\nСтатус: {('опубликован' if x.is_active else 'черновик')}\nГотовность: {escape_html(readiness)}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Предпросмотр урока', callback_data=f'admin:lesson:preview:{x.id}')], [InlineKeyboardButton(text='Добавить текст', callback_data=f'admin:lesson:text:{x.id}'), InlineKeyboardButton(text='Добавить вопрос', callback_data=f'admin:lesson:q:{x.id}')], [InlineKeyboardButton(text='Добавить фото, видео или файл', callback_data=f'admin:lesson:media:{x.id}')], [InlineKeyboardButton(text='Содержимое урока', callback_data=f'admin:lesson:content:{x.id}'), InlineKeyboardButton(text='Вопросы урока', callback_data=f'admin:lesson:questions:{x.id}')], [InlineKeyboardButton(text='Изменить название', callback_data=f'admin:lesson:rename:{x.id}')], [InlineKeyboardButton(text='Переместить выше', callback_data=f'admin:lesson:move:{x.id}:-1'), InlineKeyboardButton(text='Переместить ниже', callback_data=f'admin:lesson:move:{x.id}:1')], [InlineKeyboardButton(text='Скрыть' if x.is_active else 'Опубликовать', callback_data=f'admin:lesson:toggle:{x.id}'), InlineKeyboardButton(text='Удалить урок', callback_data=danger_callback(f'admin:lesson:delete:{x.id}'))]]))

@router.callback_query(F.data.regexp('^admin:lesson:text:\\d+$'))
async def lesson_text(c: CallbackQuery, state: FSMContext):
    lid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(lesson_id=lid, return_cb=f'admin:lesson:{lid}')
    await state.set_state(LessonAdminState.add_text)
    await c.answer()
    await c.message.answer('Отправьте текстовый блок:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.add_text)
async def lesson_text_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).add_lesson_text(d['lesson_id'], m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, 'Текст добавлен.')

@router.callback_query(F.data.regexp('^admin:lesson:media:\\d+$'))
async def lesson_media_prompt(c: CallbackQuery, state: FSMContext):
    lid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(lesson_media_id=lid, return_cb=f'admin:lesson:{lid}')
    await state.set_state(LessonAdminState.add_media)
    await c.answer()
    await c.message.answer('Отправьте фото, видео или документ одним сообщением.', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.add_media, F.photo | F.video | F.document)
@router.message(MaterialAdminState.add_media, F.photo | F.video | F.document)
async def lesson_or_material_media(m: Message, state: FSMContext, session):
    d = await state.get_data()
    if 'lesson_media_id' in d:
        if m.photo:
            typ, file_id = (MediaType.PHOTO, m.photo[-1].file_id)
        elif m.video:
            typ, file_id = (MediaType.VIDEO, m.video.file_id)
        else:
            typ, file_id = (MediaType.DOCUMENT, m.document.file_id)
        try:
            await AdminCrudService(session).add_lesson_media(d['lesson_media_id'], typ, file_id, m.caption)
        except AppError as e:
            return await m.answer(str(e))
        await finish_state(m, state, 'Медиа добавлено.')
        return
    if 'material_media_id' in d:
        if m.photo:
            typ, file_id = (MediaType.PHOTO, m.photo[-1].file_id)
        elif m.video:
            typ, file_id = (MediaType.VIDEO, m.video.file_id)
        else:
            typ, file_id = (MediaType.DOCUMENT, m.document.file_id)
        try:
            await AdminCrudService(session).add_material_media(d['material_media_id'], typ, file_id)
        except AppError as e:
            return await m.answer(str(e))
        await finish_state(m, state, 'Вложение добавлено.')
        return

@router.message(LessonAdminState.add_media)
@router.message(MaterialAdminState.add_media)
async def invalid_media_input(m: Message):
    await m.answer(
        'Ожидается фото, видео или документ. Отправьте файл или нажмите «Отменить и вернуться».',
        reply_markup=cancel_keyboard(),
    )

@router.callback_query(F.data.regexp('^admin:lesson:q:\\d+$'))
async def lesson_q(c: CallbackQuery, state: FSMContext):
    lid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(lesson_id=lid, return_cb=f'admin:lesson:{lid}')
    await state.set_state(LessonAdminState.add_question_text)
    await c.answer()
    await c.message.answer('Текст вопроса:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.add_question_text)
async def lesson_q_text(m: Message, state: FSMContext):
    await state.update_data(question_text=m.text or '')
    await state.set_state(LessonAdminState.add_question_options)
    await m.answer('Варианты ответа — каждый с новой строки. Перед правильным поставьте `+`.\nНапример:\n+Правильный\nНеверный', parse_mode='Markdown', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.add_question_options)
async def lesson_q_options(m: Message, state: FSMContext, session):
    d = await state.get_data()
    lines = [x.strip() for x in (m.text or '').splitlines() if x.strip()]
    correct = [i for i, x in enumerate(lines) if x.startswith('+')]
    if len(correct) != 1:
        return await m.answer('Должен быть ровно один вариант с `+`.')
    opts = [x[1:].strip() if x.startswith('+') else x for x in lines]
    try:
        await AdminCrudService(session).add_lesson_question(d['lesson_id'], d['question_text'], opts, correct[0])
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, 'Вопрос добавлен.')

@router.callback_query(F.data.regexp('^admin:lesson:toggle:\\d+$'))
async def lesson_toggle(c: CallbackQuery, session):
    try:
        x = await AdminCrudService(session).toggle_lesson(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Опубликован' if x.is_active else 'Скрыт', show_alert=True)

async def _show_exam_page(c: CallbackQuery, session, page: int):
    service = AdminCrudService(session)
    total, active = await service.exam_question_counts()
    page = min(max(0, page), max(0, (total - 1) // PAGE_SIZE))
    chunk = await service.exam_questions(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    rows = [[InlineKeyboardButton(text=f"{('Активен - ' if x.is_active else 'Отключён - ')}#{x.id} {x.text[:35]}", callback_data=f'admin:exam:q:{x.id}')] for x in chunk]
    rows += pager('admin:exam:p', page, total)
    rows.append([InlineKeyboardButton(text='Добавить вопрос', callback_data='admin:exam:create')])
    await c.answer()
    await c.message.answer(f'Банк экзамена: {active} активных / {total} всего\nЭкзамен: 30 вопросов, минимум один по каждой активной теме.\nСтраница {page + 1}.', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:exam')
async def exam(c: CallbackQuery, session):
    await _show_exam_page(c, session, 0)

@router.callback_query(F.data.regexp(r'^admin:exam:p:\d+$'))
async def exam_page(c: CallbackQuery, session):
    await _show_exam_page(c, session, int(c.data.rsplit(':', 1)[1]))

@router.callback_query(F.data == 'admin:exam:create')
async def exam_create(c: CallbackQuery, state: FSMContext, session):
    lessons = await AdminCrudService(session).lessons()
    if not lessons:
        return await c.answer('Сначала создайте хотя бы один урок.', show_alert=True)
    await state.update_data(return_cb='admin:exam')
    await state.set_state(ExamAdminState.choose_lesson)
    rows = [[InlineKeyboardButton(text=x.title, callback_data=f'admin:exam:lesson:{x.id}')] for x in lessons]
    rows.append([InlineKeyboardButton(text='Отменить и вернуться', callback_data='fsm:cancel')])
    await c.answer()
    await c.message.answer('К какой теме относится вопрос?', reply_markup=kb(rows))

@router.callback_query(ExamAdminState.choose_lesson, F.data.regexp('^admin:exam:lesson:\\d+$'))
async def exam_lesson(c: CallbackQuery, state: FSMContext):
    await state.update_data(exam_lesson_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(ExamAdminState.question_text)
    await c.answer()
    await c.message.answer('Текст экзаменационного вопроса:', reply_markup=cancel_keyboard())

@router.message(ExamAdminState.question_text)
async def exam_q_text(m: Message, state: FSMContext):
    await state.update_data(exam_text=m.text or '')
    await state.set_state(ExamAdminState.question_options)
    await m.answer('Варианты ответа: каждый с новой строки, перед правильным поставьте +.', reply_markup=cancel_keyboard())

@router.message(ExamAdminState.question_options)
async def exam_q_opts(m: Message, state: FSMContext, session):
    d = await state.get_data()
    lines = [x.strip() for x in (m.text or '').splitlines() if x.strip()]
    correct = [i for i, x in enumerate(lines) if x.startswith('+')]
    if len(correct) != 1:
        return await m.answer('Нужен ровно один правильный вариант с `+`.')
    opts = [x[1:].strip() if x.startswith('+') else x for x in lines]
    try:
        q = await AdminCrudService(session).create_exam_question(d['exam_lesson_id'], d['exam_text'], opts, correct[0])
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Вопрос #{q.id} создан как черновик.')

@router.callback_query(F.data.regexp('^admin:exam:q:\\d+$'))
async def exam_card(c: CallbackQuery, session):
    q = await AdminCrudService(session).exam_question(int(c.data.rsplit(':', 1)[1]))
    if not q:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    options = '\n'.join(f"{x.position}. {escape_html(x.text)}{'  [правильный]' if x.is_correct else ''}" for x in sorted(q.options, key=lambda z: z.position))
    await c.message.answer(f'<b>{escape_html(q.text)}</b>\nТема: {escape_html(q.lesson.title)}\nСтатус: {"активен" if q.is_active else "черновик"}\n\n<b>Варианты ответа</b>\n{options}', parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Изменить текст', callback_data=f'admin:exam:edittext:{q.id}'), InlineKeyboardButton(text='Варианты ответа', callback_data=f'admin:exam:options:{q.id}')], [InlineKeyboardButton(text='Сменить тему', callback_data=f'admin:exam:edittopic:{q.id}')], [InlineKeyboardButton(text='Отключить' if q.is_active else 'Включить', callback_data=f'admin:exam:toggle:{q.id}'), InlineKeyboardButton(text='Удалить вопрос', callback_data=danger_callback(f'admin:exam:delete:{q.id}'))]]))

@router.callback_query(F.data.regexp('^admin:exam:toggle:\\d+$'))
async def exam_toggle(c: CallbackQuery, session):
    try:
        q = await AdminCrudService(session).toggle_exam_question(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Активирован' if q.is_active else 'Отключён', show_alert=True)

@router.callback_query(F.data == 'admin:materials')
async def materials(c: CallbackQuery, session):
    cats = await AdminCrudService(session).categories()
    rows = [[InlineKeyboardButton(text=x.name, callback_data=f'admin:mat:cat:{x.id}')] for x in cats]
    rows.append([InlineKeyboardButton(text='Добавить категорию', callback_data='admin:mat:cat:create')])
    await c.answer()
    await c.message.answer('Материалы', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:mat:cat:create')
async def cat_create(c: CallbackQuery, state: FSMContext):
    await state.update_data(return_cb='admin:materials')
    await state.set_state(MaterialAdminState.category_name)
    await c.answer()
    await c.message.answer('Название категории:', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.category_name)
async def cat_name(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_category(m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Категория «{escape_html(x.name)}» создана.', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:mat:cat:\\d+$'))
async def cat_card(c: CallbackQuery, session):
    cid = int(c.data.rsplit(':', 1)[1])
    items = await AdminCrudService(session).materials(cid)
    rows = [[InlineKeyboardButton(text=f"{('Активен -' if x.is_active else 'Отключён -')} {x.title}", callback_data=f'admin:mat:item:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='Добавить материал', callback_data=f'admin:mat:create:{cid}')])
    rows.append([InlineKeyboardButton(text='Переименовать категорию', callback_data=f'admin:mat:cat:rename:{cid}'), InlineKeyboardButton(text='Удалить категорию', callback_data=danger_callback(f'admin:mat:cat:delete:{cid}'))])
    await c.answer()
    await c.message.answer('Материалы категории:', reply_markup=kb(rows))

@router.callback_query(F.data.regexp('^admin:mat:create:\\d+$'))
async def mat_create(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(material_category_id=cid, return_cb=f'admin:mat:cat:{cid}')
    await state.set_state(MaterialAdminState.material_title)
    await c.answer()
    await c.message.answer('Название материала:', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.material_title)
async def mat_title(m: Message, state: FSMContext):
    await state.update_data(material_title=m.text or '')
    await state.set_state(MaterialAdminState.material_content)
    await m.answer('Введите текст материала. Если материал будет только из вложений, отправьте -.', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.material_content)
async def mat_content(m: Message, state: FSMContext, session):
    d = await state.get_data()
    content = None if (m.text or '').strip() == '-' else m.text
    try:
        x = await AdminCrudService(session).create_material(d['material_category_id'], d['material_title'], content)
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Материал #{x.id} создан как черновик.')

@router.callback_query(F.data.regexp('^admin:mat:item:\\d+$'))
async def mat_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).material(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f"<b>{escape_html(x.title)}</b>\nТекст: {('есть' if x.content else 'нет')}\nВложений: {len(x.media)}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Название', callback_data=f'admin:mat:edit:title:{x.id}'), InlineKeyboardButton(text='Текст', callback_data=f'admin:mat:edit:content:{x.id}')], [InlineKeyboardButton(text='Добавить вложение', callback_data=f'admin:mat:media:{x.id}'), InlineKeyboardButton(text='Вложения', callback_data=f'admin:mat:media:list:{x.id}')], [InlineKeyboardButton(text='Переместить выше', callback_data=f'admin:mat:move:{x.id}:-1'), InlineKeyboardButton(text='Переместить ниже', callback_data=f'admin:mat:move:{x.id}:1')], [InlineKeyboardButton(text='Удалить', callback_data=danger_callback(f'admin:mat:delete:{x.id}'))], [InlineKeyboardButton(text='Скрыть' if x.is_active else 'Опубликовать', callback_data=f'admin:mat:toggle:{x.id}')]]))

@router.callback_query(F.data.regexp('^admin:mat:media:\\d+$'))
async def mat_media(c: CallbackQuery, state: FSMContext):
    mid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(material_media_id=mid, return_cb=f'admin:mat:item:{mid}')
    await state.set_state(MaterialAdminState.add_media)
    await c.answer()
    await c.message.answer('Отправьте фото, видео или документ.', reply_markup=cancel_keyboard())

@router.callback_query(F.data.regexp('^admin:mat:toggle:\\d+$'))
async def mat_toggle(c: CallbackQuery, session):
    try:
        x = await AdminCrudService(session).toggle_material(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Опубликован' if x.is_active else 'Скрыт', show_alert=True)

@router.callback_query(F.data.regexp('^admin:user:results:\\d+$'))
async def aur(c: CallbackQuery, session):
    try:
        u, p, t, e, w = await AdminCrudService(session).user_results(int(c.data.rsplit(':', 1)[1]))
    except AppError as exc:
        return await c.answer(str(exc), show_alert=True)
    last = e[0] if e else None
    wt = ', '.join((f'{k} ({v})' for k, v in w.most_common())) or 'нет'
    await c.answer()
    await c.message.answer(f"<b>{escape_html(u.full_name)}</b>\nУроки: {sum((x.status.value == 'passed' for x in p))}/{len(p)}\nПопыток тестов: {len(t)}\nПопыток экзамена: {len(e)}\nПоследний: {(last.correct_count if last else '-')} / {(last.total_count if last else '-')}\nСлабые темы: {escape_html(wt)}", parse_mode='HTML')

async def _show_exam_history(c: CallbackQuery, session, page: int):
    page = max(0, page)
    service = AdminCrudService(session)
    total = await service.exam_history_count()
    if total and page * PAGE_SIZE >= total:
        page = max(0, (total - 1) // PAGE_SIZE)
    chunk = await service.exam_history(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    rows = [[InlineKeyboardButton(text=f"{('Пройден - ' if a.passed else 'Не пройден - ')}{u.full_name[:20]} {a.correct_count}/{a.total_count}", callback_data=f'admin:user:results:{u.id}')] for a, u in chunk]
    rows += pager('admin:exam:history:p', page, total)
    await c.answer()
    await c.message.answer(f'История экзаменов: {total}. Страница {page + 1}.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data == 'admin:exam:history')
async def aeh(c: CallbackQuery, session):
    await _show_exam_history(c, session, 0)

@router.callback_query(F.data.regexp(r'^admin:exam:history:p:\d+$'))
async def aeh_page(c: CallbackQuery, session):
    await _show_exam_history(c, session, int(c.data.rsplit(':', 1)[1]))

@router.callback_query(F.data.regexp('^admin:lesson:rename:\\d+$'))
async def alr(c: CallbackQuery, state: FSMContext):
    eid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(eid=eid, return_cb=f'admin:lesson:{eid}')
    await state.set_state(LessonAdminState.edit_title)
    await c.answer()
    await c.message.answer('Новое название:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_title)
async def alrv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).rename_lesson(d['eid'], m.text or '')
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Название изменено.')

@router.callback_query(F.data.regexp('^admin:lesson:move:\\d+:-?1$'))
async def alm(c: CallbackQuery, session):
    _, _, _, i, d = c.data.split(':')
    try:
        x = await AdminCrudService(session).move_lesson(int(i), int(d))
    except AppError as exc:
        return await c.answer(str(exc), show_alert=True)
    await c.answer(f'Позиция {x.position}', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:delete:\\d+$'))
async def ald(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_lesson(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Удалено, позиции пересчитаны', show_alert=True)

@router.callback_query(F.data.regexp('^admin:exam:edittext:\\d+$'))
async def aet(c: CallbackQuery, state: FSMContext):
    eid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(eid=eid, return_cb=f'admin:exam:q:{eid}')
    await state.set_state(ExamAdminState.edit_text)
    await c.answer()
    await c.message.answer('Новый текст:', reply_markup=cancel_keyboard())

@router.message(ExamAdminState.edit_text)
async def aetv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_exam_text(d['eid'], m.text or '')
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Текст вопроса изменён.')

@router.callback_query(F.data.regexp('^admin:exam:editopts:\\d+$'))
async def aeo(c: CallbackQuery, state: FSMContext):
    eid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(eid=eid, return_cb=f'admin:exam:options:{eid}')
    await state.set_state(ExamAdminState.edit_options)
    await c.answer()
    await c.message.answer('Варианты по строкам, правильный с +', reply_markup=cancel_keyboard())

@router.message(ExamAdminState.edit_options)
async def aeov(m: Message, state: FSMContext, session):
    d = await state.get_data()
    ls = [x.strip() for x in (m.text or '').splitlines() if x.strip()]
    co = [i for i, x in enumerate(ls) if x.startswith('+')]
    if len(co) != 1:
        return await m.answer('Нужен ровно один +')
    try:
        await AdminCrudService(session).edit_exam_options(d['eid'], [x[1:].strip() if x.startswith('+') else x for x in ls], co[0])
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Варианты ответа изменены.')

@router.callback_query(F.data.regexp('^admin:exam:edittopic:\\d+$'))
async def aetp(c: CallbackQuery, session):
    q = int(c.data.rsplit(':', 1)[1])
    ls = await AdminCrudService(session).lessons()
    await c.answer()
    await c.message.answer('Новая тема:', reply_markup=kb([[InlineKeyboardButton(text=x.title, callback_data=f'admin:exam:settopic:{q}:{x.id}')] for x in ls]))

@router.callback_query(F.data.regexp('^admin:exam:settopic:\\d+:\\d+$'))
async def aest(c: CallbackQuery, session):
    _, _, _, q, l = c.data.split(':')
    try:
        await AdminCrudService(session).change_exam_lesson(int(q), int(l))
    except AppError as exc:
        return await c.answer(str(exc), show_alert=True)
    await c.answer('Изменено', show_alert=True)

@router.callback_query(F.data.regexp('^admin:exam:delete:\\d+$'))
async def aed(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_exam_question(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Удалено', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:edit:title:\\d+$'))
async def amet(c: CallbackQuery, state: FSMContext):
    eid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(eid=eid, return_cb=f'admin:mat:item:{eid}')
    await state.set_state(MaterialAdminState.edit_title)
    await c.answer()
    await c.message.answer('Новое название:', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.edit_title)
async def ametv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_material_title(d['eid'], m.text or '')
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Название материала изменено.')

@router.callback_query(F.data.regexp('^admin:mat:edit:content:\\d+$'))
async def amec(c: CallbackQuery, state: FSMContext):
    eid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(eid=eid, return_cb=f'admin:mat:item:{eid}')
    await state.set_state(MaterialAdminState.edit_content)
    await c.answer()
    await c.message.answer('Новый текст, - чтобы убрать:', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.edit_content)
async def amecv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_material_content(d['eid'], None if (m.text or '').strip() == '-' else m.text)
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Текст материала изменён.')

@router.callback_query(F.data.regexp('^admin:mat:move:\\d+:-?1$'))
async def amm(c: CallbackQuery, session):
    _, _, _, i, d = c.data.split(':')
    try:
        x = await AdminCrudService(session).move_material(int(i), int(d))
    except AppError as exc:
        return await c.answer(str(exc), show_alert=True)
    await c.answer(f'Позиция {x.position}', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:delete:\\d+$'))
async def amd(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_material(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Удалено, позиции пересчитаны', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:content:\\d+$'))
async def lesson_content_list(c: CallbackQuery, session):
    lesson = await AdminCrudService(session).lesson(int(c.data.rsplit(':', 1)[1]))
    if not lesson:
        return await c.answer('Урок не найден', show_alert=True)
    rows = []
    for item in lesson.media:
        label = f"{item.position}. {('Текст' if item.media_type == MediaType.TEXT else item.media_type.value)}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f'admin:lesson:content:item:{lesson.id}:{item.id}')])
    await c.answer()
    await c.message.answer('Контент урока:' if rows else 'Контент пуст.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp(r'^admin:lesson:content:item:\d+:\d+$'))
async def lesson_content_item(c: CallbackQuery, session):
    _, _, _, _, lid, mid = c.data.split(':')
    item = await AdminCrudService(session).lesson_media_item(int(mid))
    if not item or item.lesson_id != int(lid):
        return await c.answer('Блок не найден', show_alert=True)
    await c.answer()
    if item.media_type == MediaType.TEXT:
        rows = [[InlineKeyboardButton(text='Редактировать текст', callback_data=f'admin:lesson:content:edit:{lid}:{mid}')], [InlineKeyboardButton(text='Удалить', callback_data=danger_callback(f'admin:lesson:content:delete:{lid}:{mid}'))]]
        text = normalize_lesson_text(item.content)
        await c.message.answer(f'Блок #{item.position}: текст')
        for start in range(0, len(text), 3900):
            await c.message.answer(text[start:start + 3900])
        await c.message.answer('Действия с блоком:', reply_markup=kb(rows))
        return
    rows = [
        [InlineKeyboardButton(text='Изменить подпись', callback_data=f'admin:lesson:content:caption:{lid}:{mid}'), InlineKeyboardButton(text='Заменить файл', callback_data=f'admin:lesson:content:replace:{lid}:{mid}')],
        [InlineKeyboardButton(text='Удалить', callback_data=danger_callback(f'admin:lesson:content:delete:{lid}:{mid}'))],
    ]
    try:
        caption = (item.content or '')[:1000] or None
        if item.media_type == MediaType.PHOTO:
            await c.message.answer_photo(item.telegram_file_id, caption=caption, reply_markup=kb(rows))
        elif item.media_type == MediaType.VIDEO:
            await c.message.answer_video(item.telegram_file_id, caption=caption, reply_markup=kb(rows))
        else:
            await c.message.answer_document(item.telegram_file_id, caption=caption, reply_markup=kb(rows))
    except TelegramAPIError:
        await c.message.answer('Файл этого блока недоступен в Telegram. Его можно заменить или удалить.', reply_markup=kb(rows))

@router.callback_query(F.data.regexp('^admin:lesson:content:edit:\\d+:\\d+$'))
async def lesson_content_edit(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, mid = c.data.split(':')
    await state.update_data(lid=int(lid), mid=int(mid), return_cb=f'admin:lesson:content:item:{lid}:{mid}')
    await state.set_state(LessonAdminState.edit_text_block)
    await c.answer()
    await c.message.answer('Новый текст блока:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_text_block)
async def lesson_content_edit_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_lesson_media_text(d['lid'], d['mid'], m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, 'Текстовый блок изменён.')

@router.callback_query(F.data.regexp(r'^admin:lesson:content:caption:\d+:\d+$'))
async def lesson_content_caption(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, mid = c.data.split(':')
    await state.update_data(lid=int(lid), mid=int(mid), return_cb=f'admin:lesson:content:item:{lid}:{mid}')
    await state.set_state(LessonAdminState.edit_media_caption)
    await c.answer()
    await c.message.answer('Введите новую подпись к файлу. Отправьте - чтобы удалить подпись.', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_media_caption)
async def lesson_content_caption_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    if not m.text:
        return await m.answer('Отправьте подпись текстом или - для удаления подписи.', reply_markup=cancel_keyboard())
    value = None if m.text.strip() == '-' else m.text
    try:
        await AdminCrudService(session).edit_lesson_media_caption(d['lid'], d['mid'], value)
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Подпись изменена.')

@router.callback_query(F.data.regexp(r'^admin:lesson:content:replace:\d+:\d+$'))
async def lesson_content_replace(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, mid = c.data.split(':')
    await state.update_data(lid=int(lid), mid=int(mid), return_cb=f'admin:lesson:content:item:{lid}:{mid}')
    await state.set_state(LessonAdminState.replace_media)
    await c.answer()
    await c.message.answer('Отправьте новое фото, видео или документ.', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.replace_media, F.photo | F.video | F.document)
async def lesson_content_replace_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    if m.photo:
        typ, file_id = MediaType.PHOTO, m.photo[-1].file_id
    elif m.video:
        typ, file_id = MediaType.VIDEO, m.video.file_id
    else:
        typ, file_id = MediaType.DOCUMENT, m.document.file_id
    try:
        await AdminCrudService(session).replace_lesson_media(d['lid'], d['mid'], typ, file_id)
    except AppError as e:
        return await m.answer(str(e), reply_markup=cancel_keyboard())
    await finish_state(m, state, 'Файл заменён. Подпись сохранена.')

@router.message(LessonAdminState.replace_media)
async def lesson_content_replace_invalid(m: Message):
    await m.answer('Ожидается фото, видео или документ. Отправьте файл или отмените действие.', reply_markup=cancel_keyboard())

@router.callback_query(F.data.regexp('^admin:lesson:content:delete:\\d+:\\d+$'))
async def lesson_content_delete(c: CallbackQuery, session):
    _, _, _, _, lid, mid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_lesson_media(int(lid), int(mid))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Блок удалён.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:questions:\\d+$'))
async def lesson_questions_list(c: CallbackQuery, session):
    lesson = await AdminCrudService(session).lesson(int(c.data.rsplit(':', 1)[1]))
    if not lesson:
        return await c.answer('Урок не найден', show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{('Активен -' if q.is_active else 'Отключён -')} {q.position}. {q.text[:35]}", callback_data=f'admin:lesson:q:item:{lesson.id}:{q.id}')] for q in lesson.questions]
    await c.answer()
    await c.message.answer('Вопросы урока:' if rows else 'Вопросов нет.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp('^admin:lesson:q:item:\\d+:\\d+$'))
async def lesson_question_card(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    q = await AdminCrudService(session).lesson_question(int(qid))
    if not q or q.lesson_id != int(lid):
        return await c.answer('Вопрос не найден', show_alert=True)
    await c.answer()
    options = '\n'.join(f"{x.position}. {escape_html(x.text)}{'  [правильный]' if x.is_correct else ''}" for x in sorted(q.options, key=lambda z: z.position))
    await c.message.answer(f'<b>{escape_html(q.text)}</b>\nСтатус: {"активен" if q.is_active else "отключён"}\n\n<b>Варианты ответа</b>\n{options}', parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='Изменить текст', callback_data=f'admin:lesson:q:edittext:{lid}:{qid}'), InlineKeyboardButton(text='Варианты ответа', callback_data=f'admin:lesson:q:options:{lid}:{qid}')], [InlineKeyboardButton(text='Отключить' if q.is_active else 'Включить', callback_data=f'admin:lesson:q:toggle:{lid}:{qid}'), InlineKeyboardButton(text='Удалить вопрос', callback_data=danger_callback(f'admin:lesson:q:delete:{lid}:{qid}'))]]))

@router.callback_query(F.data.regexp('^admin:lesson:q:edittext:\\d+:\\d+$'))
async def lesson_q_edittext(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, qid = c.data.split(':')
    await state.update_data(lid=int(lid), qid=int(qid), return_cb=f'admin:lesson:q:item:{lid}:{qid}')
    await state.set_state(LessonAdminState.edit_question_text)
    await c.answer()
    await c.message.answer('Новый текст вопроса:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_question_text)
async def lesson_q_edittext_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_lesson_question_text(d['lid'], d['qid'], m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, 'Вопрос изменён.')

@router.callback_query(F.data.regexp('^admin:lesson:q:editopts:\\d+:\\d+$'))
async def lesson_q_editopts(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, qid = c.data.split(':')
    await state.update_data(lid=int(lid), qid=int(qid), return_cb=f'admin:lesson:q:options:{lid}:{qid}')
    await state.set_state(LessonAdminState.edit_question_options)
    await c.answer()
    await c.message.answer('Варианты по одному на строку. Правильный отметьте +', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_question_options)
async def lesson_q_editopts_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    lines = [x.strip() for x in (m.text or '').splitlines() if x.strip()]
    correct = [i for i, x in enumerate(lines) if x.startswith('+')]
    if len(correct) != 1:
        return await m.answer('Нужен ровно один правильный вариант с +.')
    options = [x[1:].strip() if x.startswith('+') else x for x in lines]
    try:
        await AdminCrudService(session).edit_lesson_question_options(d['lid'], d['qid'], options, correct[0])
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, 'Варианты изменены.')

@router.callback_query(F.data.regexp('^admin:lesson:q:toggle:\\d+:\\d+$'))
async def lesson_q_toggle(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    try:
        q = await AdminCrudService(session).toggle_lesson_question(int(lid), int(qid))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Включён' if q.is_active else 'Отключён', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:q:delete:\\d+:\\d+$'))
async def lesson_q_delete(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_lesson_question(int(lid), int(qid))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Вопрос удалён.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:cat:rename:\\d+$'))
async def material_category_rename(c: CallbackQuery, state: FSMContext):
    cid = int(c.data.rsplit(':', 1)[1])
    await state.update_data(category_id=cid, return_cb=f'admin:mat:cat:{cid}')
    await state.set_state(MaterialAdminState.category_rename)
    await c.answer()
    await c.message.answer('Новое название категории:', reply_markup=cancel_keyboard())

@router.message(MaterialAdminState.category_rename)
async def material_category_rename_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        x = await AdminCrudService(session).rename_category(d['category_id'], m.text or '')
    except AppError as e:
        return await m.answer(str(e))
    await finish_state(m, state, f'Категория переименована: {escape_html(x.name)}', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:mat:cat:delete:\\d+$'))
async def material_category_delete(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_category(int(c.data.rsplit(':', 1)[1]))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Категория удалена, позиции пересчитаны.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:media:list:\\d+$'))
async def material_media_list(c: CallbackQuery, session):
    item = await AdminCrudService(session).material(int(c.data.rsplit(':', 1)[1]))
    if not item:
        return await c.answer('Материал не найден', show_alert=True)
    rows = [[InlineKeyboardButton(text=f'{x.position}. {x.media_type.value}', callback_data=danger_callback(f'admin:mat:media:delete:{item.id}:{x.id}'))] for x in item.media]
    await c.answer()
    await c.message.answer('Вложения:' if rows else 'Вложений нет.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp('^admin:mat:media:delete:\\d+:\\d+$'))
async def material_media_delete(c: CallbackQuery, session):
    _, _, _, _, mid, fid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_material_media(int(mid), int(fid))
    except AppError as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Вложение удалено.', show_alert=True)


# --- Fine-grained answer option management ---
@router.callback_query(F.data.regexp(r'^admin:lesson:q:options:\d+:\d+$'))
async def lesson_options(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    q = await AdminCrudService(session).lesson_question(int(qid))
    if not q or q.lesson_id != int(lid):
        return await c.answer('Вопрос не найден', show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{x.position}. {x.text[:35]}{' [верный]' if x.is_correct else ''}", callback_data=f'admin:lesson:q:opt:{lid}:{qid}:{x.id}')] for x in sorted(q.options, key=lambda z: z.position)]
    rows.append([InlineKeyboardButton(text='Заменить все варианты', callback_data=f'admin:lesson:q:editopts:{lid}:{qid}')])
    await c.answer(); await c.message.answer('Выберите вариант ответа для редактирования:', reply_markup=kb(rows))

@router.callback_query(F.data.regexp(r'^admin:lesson:q:opt:\d+:\d+:\d+$'))
async def lesson_option_card(c: CallbackQuery, session):
    _, _, _, _, lid, qid, oid = c.data.split(':')
    q = await AdminCrudService(session).lesson_question(int(qid)); opt = next((x for x in q.options if x.id == int(oid)), None) if q else None
    if not q or q.lesson_id != int(lid) or not opt: return await c.answer('Вариант не найден', show_alert=True)
    rows=[[InlineKeyboardButton(text='Изменить текст', callback_data=f'admin:lesson:q:opt:edit:{lid}:{qid}:{oid}')]]
    if not opt.is_correct: rows.append([InlineKeyboardButton(text='Сделать правильным', callback_data=f'admin:lesson:q:opt:correct:{lid}:{qid}:{oid}')])
    rows.append([InlineKeyboardButton(text='Удалить вариант', callback_data=danger_callback(f'admin:lesson:q:opt:delete:{lid}:{qid}:{oid}'))])
    await c.answer(); await c.message.answer(f'Вариант {opt.position}: <b>{escape_html(opt.text)}</b>\nСтатус: {"правильный" if opt.is_correct else "неправильный"}', parse_mode='HTML', reply_markup=kb(rows))

@router.callback_query(F.data.regexp(r'^admin:lesson:q:opt:edit:\d+:\d+:\d+$'))
async def lesson_option_edit(c: CallbackQuery, state: FSMContext):
    _,_,_,_,_,lid,qid,oid=c.data.split(':'); await state.update_data(lid=int(lid), qid=int(qid), oid=int(oid), return_cb=f'admin:lesson:q:opt:{lid}:{qid}:{oid}'); await state.set_state(LessonAdminState.edit_option_text); await c.answer(); await c.message.answer('Введите новый текст варианта ответа:', reply_markup=cancel_keyboard())

@router.message(LessonAdminState.edit_option_text)
async def lesson_option_edit_value(m: Message, state: FSMContext, session):
    d=await state.get_data()
    try: await AdminCrudService(session).edit_lesson_option_text(d['lid'],d['qid'],d['oid'],m.text or '')
    except AppError as e: return await m.answer(str(e))
    await finish_state(m, state, 'Вариант ответа изменён.')

@router.callback_query(F.data.regexp(r'^admin:lesson:q:opt:correct:\d+:\d+:\d+$'))
async def lesson_option_correct(c: CallbackQuery, session):
    _,_,_,_,_,lid,qid,oid=c.data.split(':')
    try: await AdminCrudService(session).set_lesson_correct_option(int(lid),int(qid),int(oid))
    except AppError as e: return await c.answer(str(e), show_alert=True)
    await c.answer('Правильный вариант изменён.', show_alert=True)

@router.callback_query(F.data.regexp(r'^admin:lesson:q:opt:delete:\d+:\d+:\d+$'))
async def lesson_option_delete(c: CallbackQuery, session):
    _,_,_,_,_,lid,qid,oid=c.data.split(':')
    try: await AdminCrudService(session).delete_lesson_option(int(lid),int(qid),int(oid))
    except AppError as e: return await c.answer(str(e), show_alert=True)
    await c.answer('Вариант удалён.', show_alert=True)

@router.callback_query(F.data.regexp(r'^admin:exam:options:\d+$'))
async def exam_options(c: CallbackQuery, session):
    qid=int(c.data.rsplit(':',1)[1]); q=await AdminCrudService(session).exam_question(qid)
    if not q: return await c.answer('Вопрос не найден', show_alert=True)
    rows=[[InlineKeyboardButton(text=f"{x.position}. {x.text[:35]}{' [верный]' if x.is_correct else ''}", callback_data=f'admin:exam:opt:{qid}:{x.id}')] for x in sorted(q.options,key=lambda z:z.position)]
    rows.append([InlineKeyboardButton(text='Заменить все варианты', callback_data=f'admin:exam:editopts:{qid}')])
    await c.answer(); await c.message.answer('Выберите вариант ответа для редактирования:', reply_markup=kb(rows))

@router.callback_query(F.data.regexp(r'^admin:exam:opt:\d+:\d+$'))
async def exam_option_card(c: CallbackQuery, session):
    _,_,_,qid,oid=c.data.split(':'); q=await AdminCrudService(session).exam_question(int(qid)); opt=next((x for x in q.options if x.id==int(oid)),None) if q else None
    if not opt: return await c.answer('Вариант не найден', show_alert=True)
    rows=[[InlineKeyboardButton(text='Изменить текст', callback_data=f'admin:exam:opt:edit:{qid}:{oid}')]]
    if not opt.is_correct: rows.append([InlineKeyboardButton(text='Сделать правильным', callback_data=f'admin:exam:opt:correct:{qid}:{oid}')])
    rows.append([InlineKeyboardButton(text='Удалить вариант', callback_data=danger_callback(f'admin:exam:opt:delete:{qid}:{oid}'))])
    await c.answer(); await c.message.answer(f'Вариант {opt.position}: <b>{escape_html(opt.text)}</b>\nСтатус: {"правильный" if opt.is_correct else "неправильный"}',parse_mode='HTML',reply_markup=kb(rows))

@router.callback_query(F.data.regexp(r'^admin:exam:opt:edit:\d+:\d+$'))
async def exam_option_edit(c: CallbackQuery,state:FSMContext):
    _,_,_,_,qid,oid=c.data.split(':'); await state.update_data(eid=int(qid),oid=int(oid), return_cb=f'admin:exam:opt:{qid}:{oid}'); await state.set_state(ExamAdminState.edit_option_text); await c.answer(); await c.message.answer('Введите новый текст варианта ответа:', reply_markup=cancel_keyboard())

@router.message(ExamAdminState.edit_option_text)
async def exam_option_edit_value(m:Message,state:FSMContext,session):
    d=await state.get_data()
    try: await AdminCrudService(session).edit_exam_option_text(d['eid'],d['oid'],m.text or '')
    except AppError as e: return await m.answer(str(e))
    await finish_state(m, state, 'Вариант ответа изменён.')

@router.callback_query(F.data.regexp(r'^admin:exam:opt:correct:\d+:\d+$'))
async def exam_option_correct(c:CallbackQuery,session):
    _,_,_,_,qid,oid=c.data.split(':')
    try: await AdminCrudService(session).set_exam_correct_option(int(qid),int(oid))
    except AppError as e: return await c.answer(str(e),show_alert=True)
    await c.answer('Правильный вариант изменён.',show_alert=True)

@router.callback_query(F.data.regexp(r'^admin:exam:opt:delete:\d+:\d+$'))
async def exam_option_delete(c:CallbackQuery,session):
    _,_,_,_,qid,oid=c.data.split(':')
    try: await AdminCrudService(session).delete_exam_option(int(qid),int(oid))
    except AppError as e: return await c.answer(str(e),show_alert=True)
    await c.answer('Вариант удалён.',show_alert=True)

@router.callback_query(F.data.regexp(r'^admin:lesson:preview:\d+$'))
async def lesson_preview(c: CallbackQuery, session):
    lid = int(c.data.rsplit(':', 1)[1])
    lesson = await AdminCrudService(session).lesson(lid)
    if not lesson:
        return await c.answer('Урок больше не существует. Обновите список.', show_alert=True)
    await c.answer()
    title = clean_lesson_title(lesson.title, lesson.position)
    await c.message.answer(f'<b>Предпросмотр урока {lesson.position}</b>\n<b>{escape_html(title)}</b>', parse_mode='HTML')
    for block in sorted(lesson.media, key=lambda x: x.position):
        try:
            if block.media_type == MediaType.TEXT:
                text = normalize_lesson_text(block.content)
                for start in range(0, len(text), 3900):
                    await c.message.answer(text[start:start + 3900])
            elif block.media_type == MediaType.PHOTO:
                await c.message.answer_photo(block.telegram_file_id, caption=normalize_lesson_text(block.content)[:1000] or None)
            elif block.media_type == MediaType.VIDEO:
                await c.message.answer_video(block.telegram_file_id, caption=normalize_lesson_text(block.content)[:1000] or None)
            elif block.media_type == MediaType.DOCUMENT:
                await c.message.answer_document(block.telegram_file_id, caption=normalize_lesson_text(block.content)[:1000] or None)
        except TelegramAPIError:
            await c.message.answer(f'Блок {block.position}: Telegram-файл недоступен. Загрузите его заново перед публикацией.')
    active_questions = [q for q in lesson.questions if q.is_active]
    if active_questions:
        await c.message.answer(f'После урока сотрудник получит тест: {len(active_questions)} вопросов, проходной балл 80%.')
        for n, q in enumerate(active_questions, 1):
            opts = '\n'.join(f'{o.position}. {o.text}' for o in sorted(q.options, key=lambda x: x.position))
            await c.message.answer(f'{n}. {q.text}\n\n{opts}')
    else:
        await c.message.answer('Активных вопросов теста пока нет.')


@router.callback_query(F.data == 'admin:analytics')
async def analytics(c: CallbackQuery, session):
    d = await AdminCrudService(session).dashboard()
    rate = (d['exams_passed'] / d['exams_total'] * 100) if d['exams_total'] else 0
    lines = [
        '<b>Сводка обучения</b>',
        f"Сотрудники: {d['users_active']} активных / {d['users_total']} всего",
        f"Уроки: {d['lessons_active']} опубликовано / {d['lessons_total']} всего",
        f"Завершённых экзаменов: {d['exams_total']}",
        f"Успешных экзаменов: {d['exams_passed']} ({rate:.0f}%)",
        f"Средний результат экзамена: {d['avg_score']:.1f}/30" if d['exams_total'] else 'Средний результат экзамена: данных пока нет',
        '',
        '<b>По студиям</b>',
    ]
    active_lessons = max(1, d['lessons_active'])
    for studio_id, name, count in d['per_studio']:
        passed = d['passed_by_studio'].get(studio_id, 0)
        denom = count * active_lessons
        pct = (passed / denom * 100) if denom else 0
        lines.append(f'{escape_html(name)}: {count} сотрудников, прогресс по урокам {pct:.0f}%')
    await c.answer()
    await c.message.answer('\n'.join(lines), parse_mode='HTML')


@router.callback_query(F.data.regexp(r'^owner:audit:\d+$'))
async def owner_audit(c: CallbackQuery, session):
    from app.core.config import settings
    if c.from_user.id != settings.owner_telegram_id:
        return await c.answer('Раздел доступен только владельцу.', show_alert=True)
    page = int(c.data.rsplit(':', 1)[1])
    rows = await AdminCrudService(session).admin_history(limit=PAGE_SIZE + 1, offset=page * PAGE_SIZE)
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    text = ['<b>История изменений администраторов</b>']
    from app.repositories.core import UserRepository
    from app.core.config import settings
    users = UserRepository(session)
    for item in rows:
        when = item.created_at.strftime('%d.%m.%Y %H:%M') if item.created_at else '-'
        actor_user = await users.by_tg(item.actor_telegram_id)
        actor = 'Владелец' if item.actor_telegram_id == settings.owner_telegram_id else (actor_user.full_name if actor_user else f'Telegram ID {item.actor_telegram_id}')
        text.append(f'{when} | {escape_html(actor)}\n{escape_html(audit_action_label(item.action))}')
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='Предыдущая страница', callback_data=f'owner:audit:{page-1}'))
    if has_next:
        nav.append(InlineKeyboardButton(text='Следующая страница', callback_data=f'owner:audit:{page+1}'))
    await c.answer()
    await c.message.answer('\n\n'.join(text) if rows else 'История изменений пока пуста.', parse_mode='HTML', reply_markup=kb([nav]) if nav else None)

@router.callback_query(F.data.startswith(('admin:', 'owner:', 'd:', 'fsm:')))
async def stale_admin_callback(c: CallbackQuery):
    await c.answer('Эта кнопка устарела. Откройте нужный раздел заново из панели.', show_alert=True)
