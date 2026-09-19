from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.bot.filters.access import IsAdminOrOwner
from app.bot.states.admin import StudioAdminState, LessonAdminState, ExamAdminState, MaterialAdminState
from app.database.models import MediaType
from app.services.admin_crud import AdminCrudService
from app.utils.text import escape_html
router = Router()
router.message.filter(IsAdminOrOwner())
router.callback_query.filter(IsAdminOrOwner())

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == '⚙️ Админ-панель')
async def menu(m: Message, state: FSMContext):
    await state.clear()
    rows = [[InlineKeyboardButton(text='👥 Сотрудники', callback_data='admin:users')], [InlineKeyboardButton(text='📊 История экзаменов', callback_data='admin:exam:history')], [InlineKeyboardButton(text='🏢 Студии', callback_data='admin:studios')], [InlineKeyboardButton(text='📚 Уроки', callback_data='admin:lessons')], [InlineKeyboardButton(text='🧠 База экзамена', callback_data='admin:exam')], [InlineKeyboardButton(text='📖 Материалы', callback_data='admin:materials')]]
    from app.core.config import settings
    if m.from_user.id == settings.owner_telegram_id:
        rows.append([InlineKeyboardButton(text='👑 Администраторы', callback_data='owner:admins')])
    await m.answer('⚙️ <b>Админ-панель</b>', parse_mode='HTML', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:users')
async def users(c: CallbackQuery, session):
    items = await AdminCrudService(session).users()
    rows = [[InlineKeyboardButton(text=f"{('🟢' if x.is_active else '⚪️')} {x.full_name}", callback_data=f'admin:user:{x.id}')] for x in items[:100]]
    await c.answer()
    await c.message.answer('👥 Сотрудники' if rows else 'Сотрудников пока нет.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp('^admin:user:\\d+$'))
async def user_card(c: CallbackQuery, session):
    u = await AdminCrudService(session).user(int(c.data.rsplit(':', 1)[1]))
    if not u:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f"👤 <b>{escape_html(u.full_name)}</b>\nСтудия: {escape_html(u.studio.name)}\nСтатус: {('активен' if u.is_active else 'отключён')}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='📊 Результаты', callback_data=f'admin:user:results:{u.id}')], [InlineKeyboardButton(text='⛔️ Отключить' if u.is_active else '✅ Включить', callback_data=f'admin:user:toggle:{u.id}')]]))

@router.callback_query(F.data.regexp('^admin:user:toggle:\\d+$'))
async def user_toggle(c: CallbackQuery, session):
    try:
        u = await AdminCrudService(session).toggle_user(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Статус изменён', show_alert=True)

@router.callback_query(F.data == 'admin:studios')
async def studios(c: CallbackQuery, session):
    items = await AdminCrudService(session).studios()
    rows = [[InlineKeyboardButton(text=f"{('🟢' if x.is_active else '⚪️')} {x.name}", callback_data=f'admin:studio:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='➕ Добавить', callback_data='admin:studio:create')])
    await c.answer()
    await c.message.answer('🏢 Студии', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:studio:create')
async def studio_create(c: CallbackQuery, state: FSMContext):
    await state.set_state(StudioAdminState.create)
    await c.answer()
    await c.message.answer('Название новой студии:')

@router.message(StudioAdminState.create)
async def studio_create_name(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_studio(m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Студия «{escape_html(x.name)}» создана.', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:studio:\\d+$'))
async def studio_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).studio(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найдена', show_alert=True)
    await c.answer()
    await c.message.answer(f"🏢 <b>{escape_html(x.name)}</b>\nСтатус: {('активна' if x.is_active else 'скрыта')}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='✏️ Переименовать', callback_data=f'admin:studio:rename:{x.id}')], [InlineKeyboardButton(text='🙈 Скрыть' if x.is_active else '👁 Включить', callback_data=f'admin:studio:toggle:{x.id}')]]))

@router.callback_query(F.data.regexp('^admin:studio:rename:\\d+$'))
async def studio_rename(c: CallbackQuery, state: FSMContext):
    await state.update_data(studio_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(StudioAdminState.rename)
    await c.answer()
    await c.message.answer('Новое название:')

@router.message(StudioAdminState.rename)
async def studio_rename_name(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        x = await AdminCrudService(session).rename_studio(d['studio_id'], m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Переименовано: {escape_html(x.name)}', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:studio:toggle:\\d+$'))
async def studio_toggle(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).toggle_studio(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Статус изменён', show_alert=True)

@router.callback_query(F.data == 'admin:lessons')
async def lessons(c: CallbackQuery, session):
    items = await AdminCrudService(session).lessons()
    rows = [[InlineKeyboardButton(text=f"{('🟢' if x.is_active else '⚪️')} {x.position}. {x.title}", callback_data=f'admin:lesson:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='➕ Новый урок', callback_data='admin:lesson:create')])
    await c.answer()
    await c.message.answer('📚 Уроки', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:lesson:create')
async def lesson_create(c: CallbackQuery, state: FSMContext):
    await state.set_state(LessonAdminState.create_title)
    await c.answer()
    await c.message.answer('Название урока:')

@router.message(LessonAdminState.create_title)
async def lesson_create_title(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_lesson(m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Черновик урока #{x.id} создан.')

@router.callback_query(F.data.regexp('^admin:lesson:\\d+$'))
async def lesson_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).lesson(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f"📚 <b>{escape_html(x.title)}</b>\nКонтент: {len(x.media)}\nВопросы: {len(x.questions)}\nСтатус: {('опубликован' if x.is_active else 'черновик')}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='➕ Текст', callback_data=f'admin:lesson:text:{x.id}'), InlineKeyboardButton(text='➕ Вопрос', callback_data=f'admin:lesson:q:{x.id}')], [InlineKeyboardButton(text='📎 Фото/видео/файл', callback_data=f'admin:lesson:media:{x.id}')], [InlineKeyboardButton(text='🧩 Контент урока', callback_data=f'admin:lesson:content:{x.id}'), InlineKeyboardButton(text='❓ Вопросы урока', callback_data=f'admin:lesson:questions:{x.id}')], [InlineKeyboardButton(text='✏️ Название', callback_data=f'admin:lesson:rename:{x.id}'), InlineKeyboardButton(text='⬆️', callback_data=f'admin:lesson:move:{x.id}:-1'), InlineKeyboardButton(text='⬇️', callback_data=f'admin:lesson:move:{x.id}:1')], [InlineKeyboardButton(text='🙈 Скрыть' if x.is_active else '👁 Опубликовать', callback_data=f'admin:lesson:toggle:{x.id}'), InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin:lesson:delete:{x.id}')]]))

@router.callback_query(F.data.regexp('^admin:lesson:text:\\d+$'))
async def lesson_text(c: CallbackQuery, state: FSMContext):
    await state.update_data(lesson_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(LessonAdminState.add_text)
    await c.answer()
    await c.message.answer('Отправьте текстовый блок:')

@router.message(LessonAdminState.add_text)
async def lesson_text_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).add_lesson_text(d['lesson_id'], m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer('✅ Текст добавлен.')

@router.callback_query(F.data.regexp('^admin:lesson:media:\\d+$'))
async def lesson_media_prompt(c: CallbackQuery, state: FSMContext):
    await state.update_data(lesson_media_id=int(c.data.rsplit(':', 1)[1]))
    await c.answer()
    await c.message.answer('Отправьте фото, видео или документ одним сообщением.')

@router.message(F.photo | F.video | F.document)
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
        except Exception as e:
            return await m.answer(str(e))
        await state.clear()
        return await m.answer('✅ Медиа добавлено.')
    if 'material_media_id' in d:
        if m.photo:
            typ, file_id = (MediaType.PHOTO, m.photo[-1].file_id)
        elif m.video:
            typ, file_id = (MediaType.VIDEO, m.video.file_id)
        else:
            typ, file_id = (MediaType.DOCUMENT, m.document.file_id)
        try:
            await AdminCrudService(session).add_material_media(d['material_media_id'], typ, file_id)
        except Exception as e:
            return await m.answer(str(e))
        await state.clear()
        return await m.answer('✅ Вложение добавлено.')

@router.callback_query(F.data.regexp('^admin:lesson:q:\\d+$'))
async def lesson_q(c: CallbackQuery, state: FSMContext):
    await state.update_data(lesson_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(LessonAdminState.add_question_text)
    await c.answer()
    await c.message.answer('Текст вопроса:')

@router.message(LessonAdminState.add_question_text)
async def lesson_q_text(m: Message, state: FSMContext):
    await state.update_data(question_text=m.text or '')
    await state.set_state(LessonAdminState.add_question_options)
    await m.answer('Варианты ответа — каждый с новой строки. Перед правильным поставьте `+`.\nНапример:\n+Правильный\nНеверный', parse_mode='Markdown')

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
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer('✅ Вопрос добавлен.')

@router.callback_query(F.data.regexp('^admin:lesson:toggle:\\d+$'))
async def lesson_toggle(c: CallbackQuery, session):
    try:
        x = await AdminCrudService(session).toggle_lesson(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Опубликован' if x.is_active else 'Скрыт', show_alert=True)

@router.callback_query(F.data == 'admin:exam')
async def exam(c: CallbackQuery, session):
    service = AdminCrudService(session)
    items = await service.exam_questions()
    active = sum((x.is_active for x in items))
    rows = [[InlineKeyboardButton(text=f"{('🟢' if x.is_active else '⚪️')} #{x.id} {x.text[:35]}", callback_data=f'admin:exam:q:{x.id}')] for x in items[:100]]
    rows.append([InlineKeyboardButton(text='➕ Новый вопрос', callback_data='admin:exam:create')])
    await c.answer()
    await c.message.answer(f'🧠 Банк экзамена: {active} активных / {len(items)} всего\nДля запуска нужно ≥30.', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:exam:create')
async def exam_create(c: CallbackQuery, state: FSMContext, session):
    lessons = await AdminCrudService(session).lessons()
    rows = [[InlineKeyboardButton(text=x.title, callback_data=f'admin:exam:lesson:{x.id}')] for x in lessons]
    await c.answer()
    await c.message.answer('К какой теме относится вопрос?', reply_markup=kb(rows))

@router.callback_query(F.data.regexp('^admin:exam:lesson:\\d+$'))
async def exam_lesson(c: CallbackQuery, state: FSMContext):
    await state.update_data(exam_lesson_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(ExamAdminState.question_text)
    await c.answer()
    await c.message.answer('Текст экзаменационного вопроса:')

@router.message(ExamAdminState.question_text)
async def exam_q_text(m: Message, state: FSMContext):
    await state.update_data(exam_text=m.text or '')
    await state.set_state(ExamAdminState.question_options)
    await m.answer('Варианты — каждый с новой строки, правильный с `+`.')

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
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Вопрос #{q.id} создан как черновик.')

@router.callback_query(F.data.regexp('^admin:exam:q:\\d+$'))
async def exam_card(c: CallbackQuery, session):
    q = await AdminCrudService(session).exam_question(int(c.data.rsplit(':', 1)[1]))
    if not q:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f'🧠 <b>{escape_html(q.text)}</b>\nТема: {escape_html(q.lesson.title)}\nВариантов: {len(q.options)}', parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='✏️ Текст', callback_data=f'admin:exam:edittext:{q.id}'), InlineKeyboardButton(text='✏️ Варианты', callback_data=f'admin:exam:editopts:{q.id}')], [InlineKeyboardButton(text='📚 Сменить тему', callback_data=f'admin:exam:edittopic:{q.id}')], [InlineKeyboardButton(text='🙈 Отключить' if q.is_active else '👁 Включить', callback_data=f'admin:exam:toggle:{q.id}'), InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin:exam:delete:{q.id}')]]))

@router.callback_query(F.data.regexp('^admin:exam:toggle:\\d+$'))
async def exam_toggle(c: CallbackQuery, session):
    try:
        q = await AdminCrudService(session).toggle_exam_question(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Активирован' if q.is_active else 'Отключён', show_alert=True)

@router.callback_query(F.data == 'admin:materials')
async def materials(c: CallbackQuery, session):
    cats = await AdminCrudService(session).categories()
    rows = [[InlineKeyboardButton(text=x.name, callback_data=f'admin:mat:cat:{x.id}')] for x in cats]
    rows.append([InlineKeyboardButton(text='➕ Категория', callback_data='admin:mat:cat:create')])
    await c.answer()
    await c.message.answer('📖 Материалы', reply_markup=kb(rows))

@router.callback_query(F.data == 'admin:mat:cat:create')
async def cat_create(c: CallbackQuery, state: FSMContext):
    await state.set_state(MaterialAdminState.category_name)
    await c.answer()
    await c.message.answer('Название категории:')

@router.message(MaterialAdminState.category_name)
async def cat_name(m: Message, state: FSMContext, session):
    try:
        x = await AdminCrudService(session).create_category(m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Категория «{escape_html(x.name)}» создана.', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:mat:cat:\\d+$'))
async def cat_card(c: CallbackQuery, session):
    cid = int(c.data.rsplit(':', 1)[1])
    items = await AdminCrudService(session).materials(cid)
    rows = [[InlineKeyboardButton(text=f"{('🟢' if x.is_active else '⚪️')} {x.title}", callback_data=f'admin:mat:item:{x.id}')] for x in items]
    rows.append([InlineKeyboardButton(text='➕ Материал', callback_data=f'admin:mat:create:{cid}')])
    rows.append([InlineKeyboardButton(text='✏️ Переименовать категорию', callback_data=f'admin:mat:cat:rename:{cid}'), InlineKeyboardButton(text='🗑 Удалить категорию', callback_data=f'admin:mat:cat:delete:{cid}')])
    await c.answer()
    await c.message.answer('Материалы категории:', reply_markup=kb(rows))

@router.callback_query(F.data.regexp('^admin:mat:create:\\d+$'))
async def mat_create(c: CallbackQuery, state: FSMContext):
    await state.update_data(material_category_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(MaterialAdminState.material_title)
    await c.answer()
    await c.message.answer('Название материала:')

@router.message(MaterialAdminState.material_title)
async def mat_title(m: Message, state: FSMContext):
    await state.update_data(material_title=m.text or '')
    await state.set_state(MaterialAdminState.material_content)
    await m.answer('Текст материала. Если будет только файл — отправьте `-`.')

@router.message(MaterialAdminState.material_content)
async def mat_content(m: Message, state: FSMContext, session):
    d = await state.get_data()
    content = None if (m.text or '').strip() == '-' else m.text
    try:
        x = await AdminCrudService(session).create_material(d['material_category_id'], d['material_title'], content)
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Материал #{x.id} создан как черновик.')

@router.callback_query(F.data.regexp('^admin:mat:item:\\d+$'))
async def mat_card(c: CallbackQuery, session):
    x = await AdminCrudService(session).material(int(c.data.rsplit(':', 1)[1]))
    if not x:
        return await c.answer('Не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f"📖 <b>{escape_html(x.title)}</b>\nТекст: {('есть' if x.content else 'нет')}\nВложений: {len(x.media)}", parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='✏️ Название', callback_data=f'admin:mat:edit:title:{x.id}'), InlineKeyboardButton(text='✏️ Текст', callback_data=f'admin:mat:edit:content:{x.id}')], [InlineKeyboardButton(text='📎 Добавить вложение', callback_data=f'admin:mat:media:{x.id}'), InlineKeyboardButton(text='🗂 Вложения', callback_data=f'admin:mat:media:list:{x.id}')], [InlineKeyboardButton(text='⬆️', callback_data=f'admin:mat:move:{x.id}:-1'), InlineKeyboardButton(text='⬇️', callback_data=f'admin:mat:move:{x.id}:1')], [InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin:mat:delete:{x.id}')], [InlineKeyboardButton(text='🙈 Скрыть' if x.is_active else '👁 Опубликовать', callback_data=f'admin:mat:toggle:{x.id}')]]))

@router.callback_query(F.data.regexp('^admin:mat:media:\\d+$'))
async def mat_media(c: CallbackQuery, state: FSMContext):
    await state.update_data(material_media_id=int(c.data.rsplit(':', 1)[1]))
    await c.answer()
    await c.message.answer('Отправьте фото, видео или документ.')

@router.callback_query(F.data.regexp('^admin:mat:toggle:\\d+$'))
async def mat_toggle(c: CallbackQuery, session):
    try:
        x = await AdminCrudService(session).toggle_material(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Опубликован' if x.is_active else 'Скрыт', show_alert=True)

@router.callback_query(F.data.regexp('^admin:user:results:\\d+$'))
async def aur(c: CallbackQuery, session):
    u, p, t, e, w = await AdminCrudService(session).user_results(int(c.data.rsplit(':', 1)[1]))
    last = e[0] if e else None
    wt = ', '.join((f'{k} ({v})' for k, v in w.most_common())) or 'нет'
    await c.answer()
    await c.message.answer(f"📊 <b>{escape_html(u.full_name)}</b>\nУроки: {sum((x.status.value == 'passed' for x in p))}/{len(p)}\nПопыток тестов: {len(t)}\nПопыток экзамена: {len(e)}\nПоследний: {(last.correct_count if last else '-')} / {(last.total_count if last else '-')}\nСлабые темы: {escape_html(wt)}", parse_mode='HTML')

@router.callback_query(F.data == 'admin:exam:history')
async def aeh(c: CallbackQuery, session):
    rows = await AdminCrudService(session).exam_history()
    await c.answer()
    await c.message.answer('История экзаменов', reply_markup=kb([[InlineKeyboardButton(text=f"{('✅' if a.passed else '❌')} {u.full_name[:20]} {a.correct_count}/{a.total_count}", callback_data=f'admin:user:results:{u.id}')] for a, u in rows]) if rows else None)

@router.callback_query(F.data.regexp('^admin:lesson:rename:\\d+$'))
async def alr(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(LessonAdminState.edit_title)
    await c.answer()
    await c.message.answer('Новое название:')

@router.message(LessonAdminState.edit_title)
async def alrv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    await AdminCrudService(session).rename_lesson(d['eid'], m.text or '')
    await state.clear()
    await m.answer('✅ Изменено')

@router.callback_query(F.data.regexp('^admin:lesson:move:\\d+:-?1$'))
async def alm(c: CallbackQuery, session):
    _, _, _, i, d = c.data.split(':')
    x = await AdminCrudService(session).move_lesson(int(i), int(d))
    await c.answer(f'Позиция {x.position}', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:delete:\\d+$'))
async def ald(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_lesson(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Удалено, позиции пересчитаны', show_alert=True)

@router.callback_query(F.data.regexp('^admin:exam:edittext:\\d+$'))
async def aet(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(ExamAdminState.edit_text)
    await c.answer()
    await c.message.answer('Новый текст:')

@router.message(ExamAdminState.edit_text)
async def aetv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    await AdminCrudService(session).edit_exam_text(d['eid'], m.text or '')
    await state.clear()
    await m.answer('✅ Изменено')

@router.callback_query(F.data.regexp('^admin:exam:editopts:\\d+$'))
async def aeo(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(ExamAdminState.edit_options)
    await c.answer()
    await c.message.answer('Варианты по строкам, правильный с +')

@router.message(ExamAdminState.edit_options)
async def aeov(m: Message, state: FSMContext, session):
    d = await state.get_data()
    ls = [x.strip() for x in (m.text or '').splitlines() if x.strip()]
    co = [i for i, x in enumerate(ls) if x.startswith('+')]
    if len(co) != 1:
        return await m.answer('Нужен ровно один +')
    await AdminCrudService(session).edit_exam_options(d['eid'], [x[1:].strip() if x.startswith('+') else x for x in ls], co[0])
    await state.clear()
    await m.answer('✅ Изменено')

@router.callback_query(F.data.regexp('^admin:exam:edittopic:\\d+$'))
async def aetp(c: CallbackQuery, session):
    q = int(c.data.rsplit(':', 1)[1])
    ls = await AdminCrudService(session).lessons()
    await c.answer()
    await c.message.answer('Новая тема:', reply_markup=kb([[InlineKeyboardButton(text=x.title, callback_data=f'admin:exam:settopic:{q}:{x.id}')] for x in ls]))

@router.callback_query(F.data.regexp('^admin:exam:settopic:\\d+:\\d+$'))
async def aest(c: CallbackQuery, session):
    _, _, _, q, l = c.data.split(':')
    await AdminCrudService(session).change_exam_lesson(int(q), int(l))
    await c.answer('Изменено', show_alert=True)

@router.callback_query(F.data.regexp('^admin:exam:delete:\\d+$'))
async def aed(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_exam_question(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Удалено', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:edit:title:\\d+$'))
async def amet(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(MaterialAdminState.edit_title)
    await c.answer()
    await c.message.answer('Новое название:')

@router.message(MaterialAdminState.edit_title)
async def ametv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    await AdminCrudService(session).edit_material_title(d['eid'], m.text or '')
    await state.clear()
    await m.answer('✅ Изменено')

@router.callback_query(F.data.regexp('^admin:mat:edit:content:\\d+$'))
async def amec(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(MaterialAdminState.edit_content)
    await c.answer()
    await c.message.answer('Новый текст, - чтобы убрать:')

@router.message(MaterialAdminState.edit_content)
async def amecv(m: Message, state: FSMContext, session):
    d = await state.get_data()
    await AdminCrudService(session).edit_material_content(d['eid'], None if (m.text or '').strip() == '-' else m.text)
    await state.clear()
    await m.answer('✅ Изменено')

@router.callback_query(F.data.regexp('^admin:mat:move:\\d+:-?1$'))
async def amm(c: CallbackQuery, session):
    _, _, _, i, d = c.data.split(':')
    x = await AdminCrudService(session).move_material(int(i), int(d))
    await c.answer(f'Позиция {x.position}', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:delete:\\d+$'))
async def amd(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_material(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
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

@router.callback_query(F.data.regexp('^admin:lesson:content:item:\\d+:\\d+$'))
async def lesson_content_item(c: CallbackQuery, session):
    _, _, _, _, lid, mid = c.data.split(':')
    item = await AdminCrudService(session).lesson_media_item(int(mid))
    if not item or item.lesson_id != int(lid):
        return await c.answer('Блок не найден', show_alert=True)
    rows = []
    if item.media_type == MediaType.TEXT:
        rows.append([InlineKeyboardButton(text='✏️ Редактировать', callback_data=f'admin:lesson:content:edit:{lid}:{mid}')])
    rows.append([InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin:lesson:content:delete:{lid}:{mid}')])
    await c.answer()
    await c.message.answer(f'Блок #{item.position}', reply_markup=kb(rows))

@router.callback_query(F.data.regexp('^admin:lesson:content:edit:\\d+:\\d+$'))
async def lesson_content_edit(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, mid = c.data.split(':')
    await state.update_data(lid=int(lid), mid=int(mid))
    await state.set_state(LessonAdminState.edit_text_block)
    await c.answer()
    await c.message.answer('Новый текст блока:')

@router.message(LessonAdminState.edit_text_block)
async def lesson_content_edit_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_lesson_media_text(d['lid'], d['mid'], m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer('✅ Текстовый блок изменён.')

@router.callback_query(F.data.regexp('^admin:lesson:content:delete:\\d+:\\d+$'))
async def lesson_content_delete(c: CallbackQuery, session):
    _, _, _, _, lid, mid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_lesson_media(int(lid), int(mid))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Блок удалён.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:questions:\\d+$'))
async def lesson_questions_list(c: CallbackQuery, session):
    lesson = await AdminCrudService(session).lesson(int(c.data.rsplit(':', 1)[1]))
    if not lesson:
        return await c.answer('Урок не найден', show_alert=True)
    rows = [[InlineKeyboardButton(text=f"{('🟢' if q.is_active else '⚪️')} {q.position}. {q.text[:35]}", callback_data=f'admin:lesson:q:item:{lesson.id}:{q.id}')] for q in lesson.questions]
    await c.answer()
    await c.message.answer('Вопросы урока:' if rows else 'Вопросов нет.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp('^admin:lesson:q:item:\\d+:\\d+$'))
async def lesson_question_card(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    q = await AdminCrudService(session).lesson_question(int(qid))
    if not q or q.lesson_id != int(lid):
        return await c.answer('Вопрос не найден', show_alert=True)
    await c.answer()
    await c.message.answer(f'❓ {escape_html(q.text)}', parse_mode='HTML', reply_markup=kb([[InlineKeyboardButton(text='✏️ Текст', callback_data=f'admin:lesson:q:edittext:{lid}:{qid}'), InlineKeyboardButton(text='✏️ Варианты', callback_data=f'admin:lesson:q:editopts:{lid}:{qid}')], [InlineKeyboardButton(text='🙈 Отключить' if q.is_active else '👁 Включить', callback_data=f'admin:lesson:q:toggle:{lid}:{qid}'), InlineKeyboardButton(text='🗑 Удалить', callback_data=f'admin:lesson:q:delete:{lid}:{qid}')]]))

@router.callback_query(F.data.regexp('^admin:lesson:q:edittext:\\d+:\\d+$'))
async def lesson_q_edittext(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, qid = c.data.split(':')
    await state.update_data(lid=int(lid), qid=int(qid))
    await state.set_state(LessonAdminState.edit_question_text)
    await c.answer()
    await c.message.answer('Новый текст вопроса:')

@router.message(LessonAdminState.edit_question_text)
async def lesson_q_edittext_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        await AdminCrudService(session).edit_lesson_question_text(d['lid'], d['qid'], m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer('✅ Вопрос изменён.')

@router.callback_query(F.data.regexp('^admin:lesson:q:editopts:\\d+:\\d+$'))
async def lesson_q_editopts(c: CallbackQuery, state: FSMContext):
    _, _, _, _, lid, qid = c.data.split(':')
    await state.update_data(lid=int(lid), qid=int(qid))
    await state.set_state(LessonAdminState.edit_question_options)
    await c.answer()
    await c.message.answer('Варианты по одному на строку. Правильный отметьте +')

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
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer('✅ Варианты изменены.')

@router.callback_query(F.data.regexp('^admin:lesson:q:toggle:\\d+:\\d+$'))
async def lesson_q_toggle(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    try:
        q = await AdminCrudService(session).toggle_lesson_question(int(lid), int(qid))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Включён' if q.is_active else 'Отключён', show_alert=True)

@router.callback_query(F.data.regexp('^admin:lesson:q:delete:\\d+:\\d+$'))
async def lesson_q_delete(c: CallbackQuery, session):
    _, _, _, _, lid, qid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_lesson_question(int(lid), int(qid))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Вопрос удалён.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:cat:rename:\\d+$'))
async def material_category_rename(c: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(c.data.rsplit(':', 1)[1]))
    await state.set_state(MaterialAdminState.category_rename)
    await c.answer()
    await c.message.answer('Новое название категории:')

@router.message(MaterialAdminState.category_rename)
async def material_category_rename_value(m: Message, state: FSMContext, session):
    d = await state.get_data()
    try:
        x = await AdminCrudService(session).rename_category(d['category_id'], m.text or '')
    except Exception as e:
        return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ Категория переименована: {escape_html(x.name)}', parse_mode='HTML')

@router.callback_query(F.data.regexp('^admin:mat:cat:delete:\\d+$'))
async def material_category_delete(c: CallbackQuery, session):
    try:
        await AdminCrudService(session).delete_category(int(c.data.rsplit(':', 1)[1]))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Категория удалена, позиции пересчитаны.', show_alert=True)

@router.callback_query(F.data.regexp('^admin:mat:media:list:\\d+$'))
async def material_media_list(c: CallbackQuery, session):
    item = await AdminCrudService(session).material(int(c.data.rsplit(':', 1)[1]))
    if not item:
        return await c.answer('Материал не найден', show_alert=True)
    rows = [[InlineKeyboardButton(text=f'🗑 {x.position}. {x.media_type.value}', callback_data=f'admin:mat:media:delete:{item.id}:{x.id}')] for x in item.media]
    await c.answer()
    await c.message.answer('Вложения:' if rows else 'Вложений нет.', reply_markup=kb(rows) if rows else None)

@router.callback_query(F.data.regexp('^admin:mat:media:delete:\\d+:\\d+$'))
async def material_media_delete(c: CallbackQuery, session):
    _, _, _, _, mid, fid = c.data.split(':')
    try:
        await AdminCrudService(session).delete_material_media(int(mid), int(fid))
    except Exception as e:
        return await c.answer(str(e), show_alert=True)
    await c.answer('Вложение удалено.', show_alert=True)
