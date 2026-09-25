import logging

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)
ADMIN_GROUPS = {'StudioAdminState', 'LessonAdminState', 'ExamAdminState', 'MaterialAdminState'}
MENU_TEXTS = {'Обучение', '📚 Обучение', 'Экзамен', '📝 Экзамен', 'Материалы',
              'Мой результат', '📊 Мой результат', 'Админ-панель', '⚙️ Админ-панель', '⚙️ Меню владельца'}


class InputGuardMiddleware(BaseMiddleware):
    """Validate the envelope before routers; never let menu text become form data."""

    async def __call__(self, handler, event, data):
        if not event.from_user:
            return None
        chat = event.message.chat if isinstance(event, CallbackQuery) and event.message else getattr(event, 'chat', None)
        if chat is None or chat.type != 'private':
            if isinstance(event, CallbackQuery):
                await event.answer('Откройте личный чат с ботом.', show_alert=True)
            elif isinstance(event, Message):
                await event.answer('Обучение доступно в личном чате с ботом.')
            return None
        state = data.get('state')
        current = await state.get_state() if state else None
        if isinstance(event, CallbackQuery):
            callback = event.data or ''
            # Database integer IDs are signed 32-bit; reject oversized values before SQL.
            if any(part.lstrip('-').isdigit() and len(part.lstrip('-')) > 9
                   for part in callback.split(':')):
                return await event.answer('Некорректная кнопка.', show_alert=True)
            if callback == 'fsm:cancel' and current and current.split(':')[0] in ADMIN_GROUPS:
                # Also lets an administrator whose rights were revoked exit their form.
                await state.clear()
                return await event.answer('Действие отменено')
        if isinstance(event, Message) and current:
            group = current.split(':')[0]
            if group in ADMIN_GROUPS and current.endswith(':choose_lesson'):
                from app.bot.handlers.admin.panel import cancel_keyboard
                return await event.answer('Выберите тему кнопкой или отмените действие.', reply_markup=cancel_keyboard())
            if group in ADMIN_GROUPS and (event.text or '').strip() in MENU_TEXTS:
                from app.bot.handlers.admin.panel import cancel_keyboard
                return await event.answer('Сначала завершите действие или отмените его.', reply_markup=cancel_keyboard())
            if group in ADMIN_GROUPS and (event.text or '').startswith('/'):
                from app.bot.handlers.admin.panel import cancel_keyboard
                return await event.answer('Сначала завершите действие или отмените его.', reply_markup=cancel_keyboard())
            if group in ADMIN_GROUPS and not current.endswith((':add_media', ':replace_media', ':choose_lesson')) and not event.text:
                return await event.answer('На этом шаге отправьте текст.')
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    """Runs outside the transaction middleware, after rollback and FSM recovery."""

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except AppError as exc:
            message = str(exc)
        except Exception:
            logger.exception('Update failed: event=%s actor=%s', type(event).__name__, getattr(event.from_user, 'id', None))
            message = 'Не удалось выполнить действие. Попробуйте ещё раз.'
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(message[:200], show_alert=True)
            else:
                await event.answer(message[:3900])
        except TelegramAPIError:
            logger.warning('Could not deliver error response', exc_info=True)
        return None
