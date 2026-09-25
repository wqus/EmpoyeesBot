import hashlib, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.config import settings
from app.core.exceptions import AppError, ContentValidationError
from app.database.models import *
from app.repositories.core import AdminRepository, UserRepository

class AccessService:

    def __init__(self, s):
        self.s = s
        self.admins = AdminRepository(s)
        self.users = UserRepository(s)

    async def admin(self, tg):
        if tg == settings.owner_telegram_id:
            return True
        user = await self.users.by_tg(tg)
        return bool(user and user.is_active and await self.admins.by_user(user.id))

class InviteService:

    def __init__(self, s):
        self.s = s
        self.users = UserRepository(s)
        self.admins = AdminRepository(s)

    def owner(self, tg):
        if tg != settings.owner_telegram_id:
            raise AppError('Только владелец')

    async def create(self, tg, creator: int | None = None):
        self.owner(tg)
        raw = secrets.token_urlsafe(32)
        h = hashlib.sha256(raw.encode()).hexdigest()
        self.s.add(AdminInvite(token_hash=h, created_by_user_id=creator, expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.admin_invite_lifetime_hours)))
        await self.s.flush()
        return raw

    async def accept(self, raw, user_id):
        h = hashlib.sha256(raw.encode()).hexdigest()
        inv = await self.s.scalar(select(AdminInvite).where(AdminInvite.token_hash == h).with_for_update())
        now = datetime.now(timezone.utc)
        if not inv or inv.used_at or inv.revoked_at or (inv.expires_at <= now):
            raise AppError('Приглашение недействительно')
        from app.services.locking import active_employee
        await active_employee(self.s, user_id)
        admin = await self.admins.by_user(user_id)
        if admin is None:
            admin = await self.admins.create(user_id)
        inv.used_at = now
        inv.used_by_user_id = user_id
        await self.s.flush()
        return admin

class ContentValidator:

    @staticmethod
    def question(q):
        e = []
        if not q.text.strip():
            e.append('пустой текст вопроса')
        if len(q.options) < 2:
            e.append('меньше двух вариантов')
        if any((not o.text.strip() for o in q.options)):
            e.append('есть пустой вариант')
        if sum((bool(o.is_correct) for o in q.options)) != 1:
            e.append('должен быть ровно один правильный ответ')
        return e

    @classmethod
    def lesson(cls, lesson):
        e = []
        if not lesson.title.strip():
            e.append('нет названия')
        if not lesson.media:
            e.append('нет контента')
        for m in lesson.media:
            if m.media_type == MediaType.TEXT and (not (m.content or '').strip()):
                e.append(f'пустой текстовый блок #{m.position}')
            if m.media_type != MediaType.TEXT and (not m.telegram_file_id):
                e.append(f'нет file_id у медиа #{m.position}')
        active = [q for q in lesson.questions if q.is_active]
        if not active:
            e.append('нет активных вопросов')
        for i, q in enumerate(active, 1):
            e += [f'вопрос {i}: {x}' for x in cls.question(q)]
        if e:
            raise ContentValidationError(e)
