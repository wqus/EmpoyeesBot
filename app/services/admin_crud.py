from uuid import uuid4
from collections import Counter
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload
from app.core.config import settings
from app.core.exceptions import AppError, ContentValidationError
from app.database.models import User, Studio, Lesson, LessonMedia, LessonQuestion, LessonAnswerOption, LessonProgress, LessonTestAttempt, LessonTestAnswer, ExamQuestion, ExamAnswerOption, ExamAnswer, ExamAttempt, MaterialCategory, Material, MaterialMedia, MediaType
from app.services.admin import ContentValidator

class AdminCrudService:

    def __init__(self, session):
        self.s = session

    async def users(self, studio_id: int | None=None):
        stmt = select(User).options(selectinload(User.studio)).order_by(User.full_name, User.id)
        if studio_id is not None:
            stmt = stmt.where(User.studio_id == studio_id)
        return list((await self.s.scalars(stmt)).all())

    async def user(self, user_id: int):
        return await self.s.scalar(select(User).where(User.id == user_id).options(selectinload(User.studio)))

    async def toggle_user(self, user_id: int):
        user = await self.user(user_id)
        if not user:
            raise AppError('Сотрудник не найден')
        if user.telegram_id == settings.owner_telegram_id:
            raise AppError('Владельца нельзя отключить')
        user.is_active = not user.is_active
        await self.s.flush()
        return user

    async def user_results(self, user_id):
        u = await self.user(user_id)
        if not u:
            raise AppError('Сотрудник не найден')
        progress = list((await self.s.scalars(select(LessonProgress).where(LessonProgress.user_id == user_id).options(selectinload(LessonProgress.lesson)).join(Lesson).order_by(Lesson.position))).all())
        tests = list((await self.s.scalars(select(LessonTestAttempt).where(LessonTestAttempt.user_id == user_id).options(selectinload(LessonTestAttempt.lesson)).order_by(LessonTestAttempt.id.desc()))).all())
        exams = list((await self.s.scalars(select(ExamAttempt).where(ExamAttempt.user_id == user_id, ExamAttempt.passed.is_not(None)).order_by(ExamAttempt.id.desc()))).all())
        weak = Counter()
        if exams:
            aa = list((await self.s.scalars(select(ExamAnswer).where(ExamAnswer.attempt_id == exams[0].id).options(selectinload(ExamAnswer.question).selectinload(ExamQuestion.lesson)))).all())
            weak = Counter((x.question.lesson.title for x in aa if x.is_correct is False))
        return (u, progress, tests, exams, weak)

    async def exam_history(self, limit=50):
        return list((await self.s.execute(select(ExamAttempt, User).join(User).where(ExamAttempt.passed.is_not(None)).order_by(ExamAttempt.id.desc()).limit(limit))).all())

    async def studios(self):
        return list((await self.s.scalars(select(Studio).order_by(Studio.name))).all())

    async def studio(self, studio_id: int):
        return await self.s.get(Studio, studio_id)

    async def create_studio(self, name: str):
        name = name.strip()
        if len(name) < 2:
            raise AppError('Название слишком короткое')
        duplicate = await self.s.scalar(select(Studio.id).where(func.lower(Studio.name) == name.lower()))
        if duplicate:
            raise AppError('Такая студия уже существует')
        obj = Studio(name=name, is_active=True)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def rename_studio(self, studio_id: int, name: str):
        obj = await self.studio(studio_id)
        if not obj:
            raise AppError('Студия не найдена')
        name = name.strip()
        if len(name) < 2:
            raise AppError('Название слишком короткое')
        duplicate = await self.s.scalar(select(Studio.id).where(func.lower(Studio.name) == name.lower(), Studio.id != studio_id))
        if duplicate:
            raise AppError('Такая студия уже существует')
        obj.name = name
        await self.s.flush()
        return obj

    async def toggle_studio(self, studio_id: int):
        obj = await self.studio(studio_id)
        if not obj:
            raise AppError('Студия не найдена')
        obj.is_active = not obj.is_active
        await self.s.flush()
        return obj

    async def lessons(self):
        return list((await self.s.scalars(select(Lesson).order_by(Lesson.position))).all())

    async def lesson(self, lesson_id: int):
        return await self.s.scalar(select(Lesson).where(Lesson.id == lesson_id).options(selectinload(Lesson.media), selectinload(Lesson.questions).selectinload(LessonQuestion.options)))

    async def create_lesson(self, title: str):
        title = title.strip()
        if len(title) < 2:
            raise AppError('Введите название урока')
        pos = (await self.s.scalar(select(func.max(Lesson.position))) or 0) + 1
        obj = Lesson(title=title, position=pos, is_active=False)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def _editable_lesson(self, lesson_id: int):
        obj = await self.lesson(lesson_id)
        if not obj:
            raise AppError('Урок не найден')
        if obj.is_active:
            raise AppError('Сначала скройте опубликованный урок')
        return obj

    async def add_lesson_text(self, lesson_id: int, content: str):
        lesson = await self._editable_lesson(lesson_id)
        content = content.strip()
        if not content:
            raise AppError('Текст пустой')
        pos = max((x.position for x in lesson.media), default=0) + 1
        obj = LessonMedia(lesson_id=lesson.id, media_type=MediaType.TEXT, content=content, position=pos)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def add_lesson_media(self, lesson_id: int, media_type: MediaType, file_id: str, caption: str | None=None):
        lesson = await self._editable_lesson(lesson_id)
        pos = max((x.position for x in lesson.media), default=0) + 1
        obj = LessonMedia(lesson_id=lesson.id, media_type=media_type, telegram_file_id=file_id, content=caption, position=pos)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def add_lesson_question(self, lesson_id: int, text: str, options: list[str], correct_index: int):
        lesson = await self._editable_lesson(lesson_id)
        text = text.strip()
        options = [x.strip() for x in options if x.strip()]
        if not text or len(options) < 2 or correct_index < 0 or (correct_index >= len(options)):
            raise AppError('Некорректный вопрос')
        pos = max((x.position for x in lesson.questions), default=0) + 1
        q = LessonQuestion(lesson_id=lesson.id, text=text, position=pos, is_active=True)
        self.s.add(q)
        await self.s.flush()
        for i, option in enumerate(options, 1):
            self.s.add(LessonAnswerOption(question_id=q.id, text=option, is_correct=i - 1 == correct_index, position=i))
        await self.s.flush()
        return q

    async def lesson_media_item(self, media_id: int):
        return await self.s.get(LessonMedia, media_id)

    async def edit_lesson_media_text(self, lesson_id: int, media_id: int, content: str):
        await self._editable_lesson(lesson_id)
        item = await self.s.get(LessonMedia, media_id)
        if not item or item.lesson_id != lesson_id or item.media_type != MediaType.TEXT:
            raise AppError('Текстовый блок не найден')
        content = content.strip()
        if not content:
            raise AppError('Текст пустой')
        item.content = content
        await self.s.flush()
        return item

    async def delete_lesson_media(self, lesson_id: int, media_id: int):
        lesson = await self._editable_lesson(lesson_id)
        item = await self.s.get(LessonMedia, media_id)
        if not item or item.lesson_id != lesson_id:
            raise AppError('Блок не найден')
        pos = item.position
        await self.s.delete(item)
        await self.s.flush()
        rows = [x for x in lesson.media if x.id != media_id]
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = 100000 + n
        await self.s.flush()
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = n
        await self.s.flush()

    async def lesson_question(self, question_id: int):
        return await self.s.scalar(select(LessonQuestion).where(LessonQuestion.id == question_id).options(selectinload(LessonQuestion.options)))

    async def edit_lesson_question_text(self, lesson_id: int, question_id: int, text: str):
        await self._editable_lesson(lesson_id)
        q = await self.lesson_question(question_id)
        if not q or q.lesson_id != lesson_id:
            raise AppError('Вопрос не найден')
        used = await self.s.scalar(select(func.count(LessonTestAnswer.id)).where(LessonTestAnswer.question_id == question_id)) or 0
        if used:
            raise AppError('Вопрос уже использовался. Отключите его и создайте новую версию.')
        text = text.strip()
        if not text:
            raise AppError('Текст вопроса пустой')
        q.text = text
        await self.s.flush()
        return q

    async def edit_lesson_question_options(self, lesson_id: int, question_id: int, options: list[str], correct_index: int):
        await self._editable_lesson(lesson_id)
        q = await self.lesson_question(question_id)
        if not q or q.lesson_id != lesson_id:
            raise AppError('Вопрос не найден')
        used = await self.s.scalar(select(func.count(LessonTestAnswer.id)).where(LessonTestAnswer.question_id == question_id)) or 0
        if used:
            raise AppError('Вопрос уже использовался. Отключите его и создайте новую версию.')
        options = [x.strip() for x in options if x.strip()]
        if len(options) < 2 or correct_index not in range(len(options)):
            raise AppError('Некорректные варианты')
        await self.s.execute(delete(LessonAnswerOption).where(LessonAnswerOption.question_id == question_id))
        for n, text in enumerate(options, 1):
            self.s.add(LessonAnswerOption(question_id=question_id, text=text, is_correct=n - 1 == correct_index, position=n))
        await self.s.flush()
        return q

    async def toggle_lesson_question(self, lesson_id: int, question_id: int):
        await self._editable_lesson(lesson_id)
        q = await self.lesson_question(question_id)
        if not q or q.lesson_id != lesson_id:
            raise AppError('Вопрос не найден')
        if not q.is_active:
            errors = ContentValidator.question(q)
            if errors:
                raise ContentValidationError(errors)
        q.is_active = not q.is_active
        await self.s.flush()
        return q

    async def delete_lesson_question(self, lesson_id: int, question_id: int):
        lesson = await self._editable_lesson(lesson_id)
        q = await self.lesson_question(question_id)
        if not q or q.lesson_id != lesson_id:
            raise AppError('Вопрос не найден')
        used = await self.s.scalar(select(func.count(LessonTestAnswer.id)).where(LessonTestAnswer.question_id == question_id)) or 0
        if used:
            raise AppError('Вопрос уже использовался. Его можно только отключить.')
        await self.s.delete(q)
        await self.s.flush()
        rows = [x for x in lesson.questions if x.id != question_id]
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = 100000 + n
        await self.s.flush()
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = n
        await self.s.flush()

    async def rename_lesson(self, i, title):
        x = await self._editable_lesson(i)
        title = title.strip()
        if len(title) < 2:
            raise AppError('Введите название урока')
        x.title = title
        await self.s.flush()
        return x

    async def move_lesson(self, i, d):
        x = await self._editable_lesson(i)
        o = await self.s.scalar(select(Lesson).where(Lesson.position == x.position + d))
        if not o:
            return x
        if o.is_active:
            raise AppError('Сначала скройте соседний урок')
        history = await self.s.scalar(select(func.count(LessonProgress.id)).where(LessonProgress.lesson_id.in_([x.id, o.id]))) or 0
        if history:
            raise AppError('Порядок этих уроков уже зафиксирован у сотрудников. После начала обучения менять последовательность нельзя.')
        old, target = (x.position, o.position)
        x.position = 1000000
        await self.s.flush()
        o.position = old
        await self.s.flush()
        x.position = target
        await self.s.flush()
        return x

    async def delete_lesson(self, i):
        x = await self._editable_lesson(i)
        used = await self.s.scalar(select(func.count(LessonTestAttempt.id)).where(LessonTestAttempt.lesson_id == i)) or 0
        eu = await self.s.scalar(select(func.count(ExamAnswer.id)).join(ExamQuestion).where(ExamQuestion.lesson_id == i)) or 0
        if used or eu:
            raise AppError('Урок уже использовался. Его можно только скрыть.')
        await self.s.execute(delete(ExamQuestion).where(ExamQuestion.lesson_id == i))
        await self.s.delete(x)
        await self.s.flush()
        rows = list((await self.s.scalars(select(Lesson).order_by(Lesson.position))).all())
        for n, z in enumerate(rows, 1):
            z.position = 100000 + n
        await self.s.flush()
        for n, z in enumerate(rows, 1):
            z.position = n
        await self.s.flush()

    async def toggle_lesson(self, lesson_id: int):
        lesson = await self.lesson(lesson_id)
        if not lesson:
            raise AppError('Урок не найден')
        if lesson.is_active:
            lesson.is_active = False
        else:
            ContentValidator.lesson(lesson)
            lesson.is_active = True
        await self.s.flush()
        return lesson

    async def exam_questions(self):
        return list((await self.s.scalars(select(ExamQuestion).options(selectinload(ExamQuestion.lesson), selectinload(ExamQuestion.options)).order_by(ExamQuestion.id))).all())

    async def exam_question(self, question_id: int):
        return await self.s.scalar(select(ExamQuestion).where(ExamQuestion.id == question_id).options(selectinload(ExamQuestion.lesson), selectinload(ExamQuestion.options)))

    async def create_exam_question(self, lesson_id: int, text: str, options: list[str], correct_index: int):
        lesson = await self.s.get(Lesson, lesson_id)
        if not lesson:
            raise AppError('Тема/урок не найден')
        text = text.strip()
        options = [x.strip() for x in options if x.strip()]
        if not text or len(options) < 2 or correct_index not in range(len(options)):
            raise AppError('Некорректный вопрос')
        q = ExamQuestion(lesson_id=lesson_id, text=text, is_active=False)
        self.s.add(q)
        await self.s.flush()
        for i, option in enumerate(options, 1):
            self.s.add(ExamAnswerOption(question_id=q.id, text=option, is_correct=i - 1 == correct_index, position=i))
        await self.s.flush()
        return q

    async def _editable_exam(self, i):
        q = await self.exam_question(i)
        if not q:
            raise AppError('Вопрос не найден')
        if q.is_active:
            raise AppError('Сначала отключите вопрос')
        return q

    async def edit_exam_text(self, i, text):
        q = await self._editable_exam(i)
        text = text.strip()
        if not text:
            raise AppError('Текст пустой')
        q.text = text
        await self.s.flush()
        return q

    async def edit_exam_options(self, i, options, correct):
        q = await self._editable_exam(i)
        if await self.s.scalar(select(func.count(ExamAnswer.id)).where(ExamAnswer.question_id == i)) or 0:
            raise AppError('По вопросу уже есть история. Создайте новую версию.')
        options = [x.strip() for x in options if x.strip()]
        if len(options) < 2 or correct not in range(len(options)):
            raise AppError('Некорректные варианты')
        await self.s.execute(delete(ExamAnswerOption).where(ExamAnswerOption.question_id == i))
        for n, t in enumerate(options, 1):
            self.s.add(ExamAnswerOption(question_id=i, text=t, is_correct=n - 1 == correct, position=n))
        await self.s.flush()
        return q

    async def change_exam_lesson(self, i, lid):
        q = await self._editable_exam(i)
        if not await self.s.get(Lesson, lid):
            raise AppError('Урок не найден')
        q.lesson_id = lid
        await self.s.flush()
        return q

    async def delete_exam_question(self, i):
        q = await self._editable_exam(i)
        if await self.s.scalar(select(func.count(ExamAnswer.id)).where(ExamAnswer.question_id == i)) or 0:
            raise AppError('Вопрос уже использовался. Его можно только отключить.')
        await self.s.delete(q)
        await self.s.flush()

    async def toggle_exam_question(self, question_id: int):
        q = await self.exam_question(question_id)
        if not q:
            raise AppError('Вопрос не найден')
        if q.is_active:
            q.is_active = False
        else:
            errors = ContentValidator.question(q)
            if errors:
                raise ContentValidationError(errors)
            q.is_active = True
        await self.s.flush()
        return q

    async def categories(self):
        return list((await self.s.scalars(select(MaterialCategory).order_by(MaterialCategory.position))).all())

    async def category(self, category_id: int):
        return await self.s.get(MaterialCategory, category_id)

    async def rename_category(self, category_id: int, name: str):
        x = await self.category(category_id)
        if not x:
            raise AppError('Категория не найдена')
        name = name.strip()
        if len(name) < 2:
            raise AppError('Введите название категории')
        x.name = name
        await self.s.flush()
        return x

    async def delete_category(self, category_id: int):
        x = await self.category(category_id)
        if not x:
            raise AppError('Категория не найдена')
        await self.s.delete(x)
        await self.s.flush()
        rows = list((await self.s.scalars(select(MaterialCategory).order_by(MaterialCategory.position))).all())
        for n, z in enumerate(rows, 1):
            z.position = 100000 + n
        await self.s.flush()
        for n, z in enumerate(rows, 1):
            z.position = n
        await self.s.flush()

    async def create_category(self, name: str):
        name = name.strip()
        if len(name) < 2:
            raise AppError('Введите название категории')
        pos = (await self.s.scalar(select(func.max(MaterialCategory.position))) or 0) + 1
        obj = MaterialCategory(name=name, slug=f'category-{uuid4().hex[:12]}', position=pos, is_active=True)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def materials(self, category_id: int):
        return list((await self.s.scalars(select(Material).where(Material.category_id == category_id).options(selectinload(Material.media)).order_by(Material.position))).all())

    async def material(self, material_id: int):
        return await self.s.scalar(select(Material).where(Material.id == material_id).options(selectinload(Material.media)))

    async def create_material(self, category_id: int, title: str, content: str | None):
        category = await self.s.get(MaterialCategory, category_id)
        if not category:
            raise AppError('Категория не найдена')
        title = title.strip()
        if len(title) < 2:
            raise AppError('Введите название материала')
        pos = (await self.s.scalar(select(func.max(Material.position)).where(Material.category_id == category_id)) or 0) + 1
        obj = Material(category_id=category_id, title=title, content=(content or '').strip() or None, position=pos, is_active=False)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def edit_material_title(self, i, title):
        x = await self.material(i)
        if not x:
            raise AppError('Материал не найден')
        if x.is_active:
            raise AppError('Сначала скройте материал')
        title = title.strip()
        if len(title) < 2:
            raise AppError('Введите название')
        x.title = title
        await self.s.flush()
        return x

    async def edit_material_content(self, i, content):
        x = await self.material(i)
        if not x:
            raise AppError('Материал не найден')
        if x.is_active:
            raise AppError('Сначала скройте материал')
        x.content = (content or '').strip() or None
        await self.s.flush()
        return x

    async def move_material(self, i, d):
        x = await self.material(i)
        if not x:
            raise AppError('Материал не найден')
        if x.is_active:
            raise AppError('Сначала скройте материал')
        o = await self.s.scalar(select(Material).where(Material.category_id == x.category_id, Material.position == x.position + d))
        if not o:
            return x
        if o.is_active:
            raise AppError('Сначала скройте соседний материал')
        old, target = (x.position, o.position)
        x.position = 1000000
        await self.s.flush()
        o.position = old
        await self.s.flush()
        x.position = target
        await self.s.flush()
        return x

    async def delete_material(self, i):
        x = await self.material(i)
        if not x:
            raise AppError('Материал не найден')
        if x.is_active:
            raise AppError('Сначала скройте материал')
        cid = x.category_id
        await self.s.delete(x)
        await self.s.flush()
        rows = list((await self.s.scalars(select(Material).where(Material.category_id == cid).order_by(Material.position))).all())
        for n, z in enumerate(rows, 1):
            z.position = 100000 + n
        await self.s.flush()
        for n, z in enumerate(rows, 1):
            z.position = n
        await self.s.flush()

    async def add_material_media(self, material_id: int, media_type: MediaType, file_id: str):
        material = await self.material(material_id)
        if not material:
            raise AppError('Материал не найден')
        if material.is_active:
            raise AppError('Сначала скройте материал')
        pos = max((x.position for x in material.media), default=0) + 1
        obj = MaterialMedia(material_id=material.id, media_type=media_type, telegram_file_id=file_id, position=pos)
        self.s.add(obj)
        await self.s.flush()
        return obj

    async def delete_material_media(self, material_id: int, media_id: int):
        material = await self.material(material_id)
        if not material:
            raise AppError('Материал не найден')
        if material.is_active:
            raise AppError('Сначала скройте материал')
        item = await self.s.get(MaterialMedia, media_id)
        if not item or item.material_id != material_id:
            raise AppError('Вложение не найдено')
        await self.s.delete(item)
        await self.s.flush()
        rows = [x for x in material.media if x.id != media_id]
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = 100000 + n
        await self.s.flush()
        for n, x in enumerate(sorted(rows, key=lambda z: z.position), 1):
            x.position = n
        await self.s.flush()

    async def toggle_material(self, material_id: int):
        material = await self.material(material_id)
        if not material:
            raise AppError('Материал не найден')
        if material.is_active:
            material.is_active = False
        else:
            errors = []
            if not material.title.strip():
                errors.append('нет названия')
            if not (material.content or '').strip() and (not material.media):
                errors.append('нет текста или вложений')
            if errors:
                raise ContentValidationError(errors)
            material.is_active = True
        await self.s.flush()
        return material
