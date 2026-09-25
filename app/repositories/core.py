from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.database.models import *

class UserRepository:

    def __init__(self, s):
        self.s = s

    async def by_tg(self, tg):
        return await self.s.scalar(select(User).where(User.telegram_id == tg).options(selectinload(User.studio)))

    async def by_id(self, i):
        return await self.s.get(User, i)

    async def create(self, **kw):
        o = User(**kw)
        self.s.add(o)
        await self.s.flush()
        return o

class StudioRepository:

    def __init__(self, s):
        self.s = s

    async def active(self):
        return list((await self.s.scalars(select(Studio).where(Studio.is_active.is_(True)).order_by(Studio.name))).all())

    async def all(self):
        return list((await self.s.scalars(select(Studio).order_by(Studio.name))).all())

    async def by_id(self, i):
        return await self.s.get(Studio, i)

class AdminRepository:

    def __init__(self, s):
        self.s = s

    async def by_user(self, i):
        return await self.s.scalar(select(Admin).where(Admin.user_id == i))

    async def by_tg(self, tg):
        return await self.s.scalar(select(Admin).join(User, User.id == Admin.user_id).where(User.telegram_id == tg))

    async def all(self):
        return list((await self.s.scalars(select(Admin).options(selectinload(Admin.user)).order_by(Admin.id))).all())

    async def create(self, i):
        o = Admin(user_id=i)
        self.s.add(o)
        await self.s.flush()
        return o

class LearningRepository:

    def __init__(self, s):
        self.s = s

    async def lessons(self):
        return list((await self.s.scalars(select(Lesson).where(Lesson.is_active.is_(True)).order_by(Lesson.position))).all())

    async def lesson(self, i):
        return await self.s.scalar(select(Lesson).where(Lesson.id == i, Lesson.is_active.is_(True)).options(selectinload(Lesson.media)))

    async def progress(self, u):
        stmt = select(LessonProgress).join(Lesson, Lesson.id == LessonProgress.lesson_id).where(LessonProgress.user_id == u, Lesson.is_active.is_(True)).options(selectinload(LessonProgress.lesson)).order_by(Lesson.position)
        return list((await self.s.scalars(stmt)).all())

    async def progress_one(self, u, l):
        return await self.s.scalar(select(LessonProgress).where(LessonProgress.user_id == u, LessonProgress.lesson_id == l))

    async def questions(self, l):
        stmt = select(LessonQuestion).where(LessonQuestion.lesson_id == l, LessonQuestion.is_active.is_(True)).options(selectinload(LessonQuestion.options)).order_by(LessonQuestion.position)
        return list((await self.s.scalars(stmt)).all())

class ExamRepository:

    def __init__(self, s):
        self.s = s

    async def count(self):
        return await self.s.scalar(select(func.count(ExamQuestion.id)).where(ExamQuestion.is_active.is_(True))) or 0

    async def random(self, n):
        stmt = select(ExamQuestion).where(ExamQuestion.is_active.is_(True)).options(selectinload(ExamQuestion.options)).order_by(func.random()).limit(n)
        return list((await self.s.scalars(stmt)).all())

    async def active_questions(self):
        stmt = (select(ExamQuestion).join(Lesson, Lesson.id == ExamQuestion.lesson_id).where(ExamQuestion.is_active.is_(True), Lesson.is_active.is_(True)).options(selectinload(ExamQuestion.options), selectinload(ExamQuestion.lesson)).order_by(ExamQuestion.id))
        return list((await self.s.scalars(stmt)).all())

    async def active_attempt(self, u):
        return await self.s.scalar(select(ExamAttempt).where(ExamAttempt.user_id == u, ExamAttempt.passed.is_(None)).order_by(ExamAttempt.id.desc()).limit(1))

    async def attempt(self, a):
        return await self.s.scalar(select(ExamAttempt).where(ExamAttempt.id == a).execution_options(populate_existing=True))

    async def answers(self, a):
        stmt = select(ExamAnswer).where(ExamAnswer.attempt_id == a).options(selectinload(ExamAnswer.question).selectinload(ExamQuestion.options), selectinload(ExamAnswer.question).selectinload(ExamQuestion.lesson)).order_by(ExamAnswer.position)
        return list((await self.s.scalars(stmt)).all())

    async def next_unanswered_for_update(self, a):
        stmt = select(ExamAnswer).where(ExamAnswer.attempt_id == a, ExamAnswer.selected_option_id.is_(None)).options(selectinload(ExamAnswer.question).selectinload(ExamQuestion.options), selectinload(ExamAnswer.question).selectinload(ExamQuestion.lesson)).order_by(ExamAnswer.position).limit(1).with_for_update()
        return await self.s.scalar(stmt)

    async def completed(self, u):
        return list((await self.s.scalars(select(ExamAttempt).where(ExamAttempt.user_id == u, ExamAttempt.passed.is_not(None)).order_by(ExamAttempt.id.desc()))).all())

class MaterialRepository:

    def __init__(self, s):
        self.s = s

    async def categories(self):
        return list((await self.s.scalars(select(MaterialCategory).where(MaterialCategory.is_active.is_(True)).order_by(MaterialCategory.position))).all())

    async def materials(self, c):
        return list((await self.s.scalars(select(Material).join(MaterialCategory).where(Material.category_id == c, Material.is_active.is_(True), MaterialCategory.is_active.is_(True)).order_by(Material.position))).all())

    async def material(self, i):
        return await self.s.scalar(select(Material).join(MaterialCategory).where(Material.id == i, Material.is_active.is_(True), MaterialCategory.is_active.is_(True)).options(selectinload(Material.media)))
