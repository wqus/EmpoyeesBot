import math
import random
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from app.core.exceptions import AppError
from app.database.models import *
from app.repositories.core import *
from app.services.locking import active_employee, catalog_lock
from sqlalchemy import text

class RegistrationService:

    def __init__(self, s):
        self.s = s
        self.users = UserRepository(s)
        self.studios = StudioRepository(s)

    async def register(self, tg, name, studio_id):
        name = name.strip()
        if not 2 <= len(name) <= 255:
            raise AppError('Введите корректное ФИО')
        await self.s.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': tg})
        if await self.users.by_tg(tg):
            raise AppError('Уже зарегистрирован')
        studio = await self.studios.by_id(studio_id)
        if not studio or not studio.is_active:
            raise AppError('Студия недоступна')
        return await self.users.create(telegram_id=tg, full_name=name, studio_id=studio_id)

class LearningService:

    def __init__(self, s):
        self.s = s
        self.r = LearningRepository(s)

    async def ensure_progress(self, u):
        await catalog_lock(self.s, shared=True)
        await active_employee(self.s, u)
        lessons = await self.r.lessons()
        existing = {p.lesson_id: p for p in await self.r.progress(u)}
        previous_passed = True
        for lesson in lessons:
            current = existing.get(lesson.id)
            if current is None:
                status = LessonProgressStatus.AVAILABLE if previous_passed else LessonProgressStatus.LOCKED
                current = LessonProgress(user_id=u, lesson_id=lesson.id, status=status)
                self.s.add(current)
            elif current.status != LessonProgressStatus.PASSED:
                current.status = LessonProgressStatus.AVAILABLE if previous_passed else LessonProgressStatus.LOCKED
            previous_passed = previous_passed and current.status == LessonProgressStatus.PASSED
        await self.s.flush()

    async def list(self, u):
        await self.ensure_progress(u)
        return await self.r.progress(u)

    async def lesson(self, u, l):
        await self.ensure_progress(u)
        p = await self.r.progress_one(u, l)
        if not p or p.status == LessonProgressStatus.LOCKED:
            raise AppError('Урок заблокирован')
        lesson = await self.r.lesson(l)
        if not lesson:
            raise AppError('Урок недоступен')
        return lesson

class LessonTestService:
    PASS = 0.8

    def __init__(self, s):
        self.s = s
        self.r = LearningRepository(s)

    @staticmethod
    def required(n):
        return math.ceil(n * 0.8)

    @staticmethod
    def revision(questions):
        snapshot = [(q.id, q.text, [(o.id, o.text, o.is_correct) for o in q.options]) for q in questions]
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False).encode()).hexdigest()

    async def questions(self, l):
        qs = await self.r.questions(l)
        if not qs:
            raise AppError('У теста нет активных вопросов')
        if any((len(q.options) < 2 or sum((bool(o.is_correct) for o in q.options)) != 1 or any((not o.text.strip() for o in q.options)) for q in qs)):
            raise AppError('Тест настроен некорректно')
        return qs

    async def finish(self, u, l, answers, *, expected_revision=None):
        await LearningService(self.s).lesson(u, l)
        progress = await self.r.progress_one(u, l)
        if not progress or progress.status == LessonProgressStatus.LOCKED:
            raise AppError('Урок недоступен')
        qs = await self.questions(l)
        if expected_revision is not None and self.revision(qs) != expected_revision:
            raise AppError('Вопросы теста изменились. Начните новую попытку.')
        by = {q.id: q for q in qs}
        if len(answers) != len(qs) or len({qid for qid, _ in answers}) != len(qs):
            raise AppError('Ответы неполные или содержат дубликаты')
        correct = 0
        checked = []
        for qid, oid in answers:
            q = by.get(qid)
            o = next((x for x in q.options if x.id == oid), None) if q else None
            if not o:
                raise AppError('Некорректный ответ')
            correct += int(o.is_correct)
            checked.append((q, o))
        passed = correct >= self.required(len(qs))
        attempt = LessonTestAttempt(user_id=u, lesson_id=l, correct_count=correct, total_count=len(qs), passed=passed)
        self.s.add(attempt)
        await self.s.flush()
        for q, o in checked:
            self.s.add(LessonTestAnswer(attempt_id=attempt.id, question_id=q.id, selected_option_id=o.id, is_correct=o.is_correct))
        if passed:
            progress.status = LessonProgressStatus.PASSED
            progress.passed_at = datetime.now(timezone.utc)
            lessons = await self.r.lessons()
            ids = [x.id for x in lessons]
            if l in ids and ids.index(l) + 1 < len(ids):
                nxt = await self.r.progress_one(u, ids[ids.index(l) + 1])
                if nxt and nxt.status == LessonProgressStatus.LOCKED:
                    nxt.status = LessonProgressStatus.AVAILABLE
        await self.s.flush()
        return (correct, len(qs), passed)

class ExamService:
    COUNT = 30
    PASS = 27

    def __init__(self, s):
        self.s = s
        self.e = ExamRepository(s)
        self.l = LearningRepository(s)

    async def start(self, u):
        await LearningService(self.s).ensure_progress(u)
        active = await self.e.active_attempt(u)
        if active:
            return active
        lessons = await self.l.lessons()
        progress = await self.l.progress(u)
        passed = {p.lesson_id for p in progress if p.status == LessonProgressStatus.PASSED}
        if not lessons or any((x.id not in passed for x in lessons)):
            raise AppError('Сначала пройдите все уроки')
        active_questions = await self.e.active_questions()
        if len(active_questions) < self.COUNT:
            raise AppError('Нужно минимум 30 активных вопросов')
        # В каждом экзамене гарантируем минимум один вопрос по каждой активной теме/уроку.
        # Остальные места заполняются случайно без повторов.
        by_lesson = {}
        for question in active_questions:
            by_lesson.setdefault(question.lesson_id, []).append(question)
        missing = [lesson.title for lesson in lessons if lesson.id not in by_lesson]
        if missing:
            raise AppError('В банке экзамена нет активных вопросов по темам: ' + ', '.join(missing))
        if len(lessons) > self.COUNT:
            raise AppError('Активных тем больше 30, невозможно включить минимум один вопрос по каждой теме')
        rng = random.SystemRandom()
        questions = [rng.choice(by_lesson[lesson.id]) for lesson in lessons]
        selected_ids = {q.id for q in questions}
        remaining = [q for q in active_questions if q.id not in selected_ids]
        rng.shuffle(remaining)
        questions.extend(remaining[: self.COUNT - len(questions)])
        rng.shuffle(questions)
        if len(questions) != self.COUNT or any((len(q.options) < 2 or sum((bool(o.is_correct) for o in q.options)) != 1 for q in questions)):
            raise AppError('Банк экзамена настроен некорректно')
        a = ExamAttempt(user_id=u, total_count=self.COUNT, correct_count=0, passed=None)
        self.s.add(a)
        await self.s.flush()
        for pos, q in enumerate(questions, 1):
            self.s.add(ExamAnswer(attempt_id=a.id, question_id=q.id, position=pos))
        await self.s.flush()
        return a

    async def current(self, u, a):
        await active_employee(self.s, u)
        att = await self.e.attempt(a)
        if not att or att.user_id != u or att.passed is not None:
            return None
        return next((x for x in await self.e.answers(a) if x.selected_option_id is None), None)

    async def answer(self, u, a, q, o):
        await active_employee(self.s, u)
        att = await self.e.attempt(a)
        if not att or att.user_id != u or att.passed is not None:
            raise AppError('Попытка недоступна')
        cur = await self.e.next_unanswered_for_update(a)
        if not cur or cur.question_id != q:
            raise AppError('Вопрос уже обработан')
        opt = next((x for x in cur.question.options if x.id == o), None)
        if not opt:
            raise AppError('Некорректный вариант')
        cur.selected_option_id = o
        cur.is_correct = opt.is_correct
        await self.s.flush()

    async def finish(self, u, a):
        await active_employee(self.s, u)
        att = await self.e.attempt(a)
        if not att or att.user_id != u or att.passed is not None:
            raise AppError('Попытка недоступна')
        ans = await self.e.answers(a)
        if len(ans) != self.COUNT or any((x.selected_option_id is None for x in ans)):
            raise AppError('Экзамен не завершён')
        att.correct_count = sum((x.is_correct is True for x in ans))
        att.total_count = len(ans)
        att.passed = att.correct_count >= self.PASS
        att.completed_at = datetime.now(timezone.utc)
        await self.s.flush()
        return att

class ResultService:

    def __init__(self, s):
        self.s = s
        self.e = ExamRepository(s)
        self.l = LearningRepository(s)

    async def summary(self, u):
        await LearningService(self.s).ensure_progress(u)
        progress = await self.l.progress(u)
        exams = await self.e.completed(u)
        last = exams[0] if exams else None
        weak = Counter()
        if last:
            answers = await self.e.answers(last.id)
            weak = Counter((x.question.lesson.title for x in answers if x.is_correct is False))
        return (progress, exams, last, weak)
