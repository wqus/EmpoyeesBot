from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from app.database.engine import async_session_factory
from app.database.models import AdminAction, ProcessedUpdate
from sqlalchemy import event, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from copy import deepcopy
import json
import hashlib

@event.listens_for(Session, "before_flush")
def _mark_successful_flush(session, flush_context, instances):
    session.info["did_flush"] = session.info.get("did_flush", False) or bool(
        session.new or session.deleted or any(session.is_modified(item) for item in session.dirty)
    )

_MUTATING_CALLBACK_PARTS = (
    ':create', ':rename', ':toggle:', ':delete:', ':move:', ':edit', ':correct:',
    ':settopic:', ':remove:', ':revoke:', ':media:delete:', ':content:delete:',
)
_ADMIN_STATE_MARKERS = ('StudioAdminState:', 'LessonAdminState:', 'ExamAdminState:', 'MaterialAdminState:')


def _callback_action(data: str) -> str | None:
    if not data or data.startswith('d:'):
        return None
    if not (data.startswith('admin:') or data.startswith('owner:')):
        return None
    if any(part in data for part in _MUTATING_CALLBACK_PARTS):
        return data[:120]
    return None


class DatabaseSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with async_session_factory() as s:
            data['session'] = s
            state = data.get('state')
            state_before = await state.get_state() if state else None
            data_before = deepcopy(await state.get_data()) if state else {}
            s.sync_session.info['did_flush'] = False
            try:
                update = data.get('event_update')
                bot = data.get('bot')
                receipt = None
                callback_key = None
                if update is not None and bot is not None:
                    inserted = await s.scalar(insert(ProcessedUpdate).values(
                        bot_id=bot.id, update_id=update.update_id,
                    ).on_conflict_do_nothing().returning(ProcessedUpdate.update_id))
                    if inserted is None:
                        if isinstance(event, CallbackQuery):
                            await event.answer('Событие уже обработано.')
                        return None
                    receipt = await s.get(ProcessedUpdate, (bot.id, update.update_id))
                if isinstance(event, CallbackQuery) and _callback_action(event.data or ''):
                    source = f'{event.bot.id}:{event.from_user.id}:{event.message.chat.id}:{event.message.message_id}:{event.data}'
                    callback_key = hashlib.sha256(source.encode()).hexdigest()
                    key = int.from_bytes(bytes.fromhex(callback_key[:16]), 'big', signed=True)
                    await s.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
                    if await s.scalar(select(ProcessedUpdate.update_id).where(ProcessedUpdate.callback_key == callback_key)) is not None:
                        await event.answer('Действие уже выполнено. Откройте раздел заново.')
                        await s.commit()
                        return None
                result = await handler(event, data)
                actor = getattr(getattr(event, 'from_user', None), 'id', None)
                action = None
                target = None
                if actor and isinstance(event, CallbackQuery):
                    action = _callback_action(event.data or '')
                    target = (event.data or '')[:255]
                elif actor and isinstance(event, Message) and state_before and any(x in state_before for x in _ADMIN_STATE_MARKERS):
                    action = f'fsm:{state_before}'[:120]
                    target = 'admin input'
                if action and s.sync_session.info.get("did_flush"):
                    if receipt is not None and callback_key:
                        receipt.callback_key = callback_key
                    identifiers = {key: value for key, value in data_before.items()
                                   if isinstance(value, int) and (key.endswith('_id') or key in {'lid', 'qid', 'oid', 'eid', 'mid', 'cid', 'sid', 'uid', 'id'})}
                    s.add(AdminAction(actor_telegram_id=actor, action=action, target=target,
                                      details=json.dumps(identifiers) if identifiers else None))
                if s.in_transaction():
                    await s.commit()
                return result
            except BaseException:
                if s.in_transaction():
                    await s.rollback()
                if state:
                    await state.set_data(data_before)
                    await state.set_state(state_before)
                raise
