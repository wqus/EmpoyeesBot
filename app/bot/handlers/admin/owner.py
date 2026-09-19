from datetime import datetime, timezone
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from app.bot.filters.access import IsOwner
from app.core.config import settings
from app.database.models import Admin, AdminInvite
from app.repositories.core import UserRepository, AdminRepository
from app.services.admin import InviteService
router = Router()
router.callback_query.filter(IsOwner())

@router.callback_query(F.data == 'owner:admins')
async def panel(c: CallbackQuery):
    await c.answer()
    await c.message.answer('👑 Управление администраторами', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='➕ Создать invite', callback_data='owner:invite:create')], [InlineKeyboardButton(text='👥 Список админов', callback_data='owner:admins:list')], [InlineKeyboardButton(text='🔗 Активные invite', callback_data='owner:invites:list')]]))

@router.callback_query(F.data == 'owner:invite:create')
async def create(c: CallbackQuery, session):
    u = await UserRepository(session).by_tg(c.from_user.id)
    if not u:
        return await c.answer('Сначала зарегистрируйтесь.', show_alert=True)
    raw = await InviteService(session).create(c.from_user.id, u.id)
    me = await c.bot.get_me()
    await c.answer()
    await c.message.answer(f'https://t.me/{me.username}?start=admin_{raw}')

@router.callback_query(F.data == 'owner:admins:list')
async def admins(c: CallbackQuery, session):
    items = await AdminRepository(session).all()
    rows = [[InlineKeyboardButton(text=f'❌ {x.user.full_name}', callback_data=f'owner:admin:remove:{x.user_id}')] for x in items]
    await c.answer()
    await c.message.answer('Администраторы:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)

@router.callback_query(F.data.regexp('^owner:admin:remove:\\d+$'))
async def remove(c: CallbackQuery, session):
    uid = int(c.data.rsplit(':', 1)[1])
    user = await UserRepository(session).by_id(uid)
    if not user:
        return await c.answer('Не найден.', show_alert=True)
    if user.telegram_id == settings.owner_telegram_id:
        return await c.answer('Владельца удалить нельзя.', show_alert=True)
    admin = await AdminRepository(session).by_user(uid)
    if admin:
        await session.delete(admin)
        await session.flush()
    await c.answer('Администратор удалён.', show_alert=True)

@router.callback_query(F.data == 'owner:invites:list')
async def invites(c: CallbackQuery, session):
    now = datetime.now(timezone.utc)
    items = list((await session.scalars(select(AdminInvite).where(AdminInvite.used_at.is_(None), AdminInvite.revoked_at.is_(None), AdminInvite.expires_at > now).order_by(AdminInvite.id.desc()))).all())
    rows = [[InlineKeyboardButton(text=f'❌ Отозвать #{x.id}', callback_data=f'owner:invite:revoke:{x.id}')] for x in items]
    await c.answer()
    await c.message.answer('Активные приглашения:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)

@router.callback_query(F.data.regexp('^owner:invite:revoke:\\d+$'))
async def revoke(c: CallbackQuery, session):
    x = await session.get(AdminInvite, int(c.data.rsplit(':', 1)[1]))
    if not x or x.used_at or x.revoked_at:
        return await c.answer('Уже недействительно.', show_alert=True)
    x.revoked_at = datetime.now(timezone.utc)
    await session.flush()
    await c.answer('Отозвано.', show_alert=True)
