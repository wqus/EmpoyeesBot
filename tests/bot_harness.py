"""Real aiogram dispatcher + real PostgreSQL; only the Telegram HTTP boundary is fake."""
import importlib
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, GetMe
from aiogram.types import Message, Update, User


class TelegramRecorder(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.fail_next = False

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield b''

    async def make_request(self, bot, method, timeout=None):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError('Injected transport failure')
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=123456, is_bot=True, first_name='Audit', username='audit_bot')
        if isinstance(method, AnswerCallbackQuery):
            assert len(method.text or '') <= 200
            return True
        text = getattr(method, 'text', None)
        if isinstance(text, str):
            assert len(text.encode('utf-16-le')) // 2 <= 4096, 'Telegram text limit exceeded'
        markup = getattr(method, 'reply_markup', None)
        if markup and hasattr(markup, 'inline_keyboard'):
            for row in markup.inline_keyboard:
                for button in row:
                    assert len((button.callback_data or '').encode()) <= 64
        return Message(message_id=len(self.calls), date=datetime.now(timezone.utc),
                       chat={'id': int(method.chat_id), 'type': 'private'}, text=text,
                       from_user={'id': bot.id, 'is_bot': True, 'first_name': 'Audit'})


class BotHarness:
    def __init__(self, dp, bot, recorder):
        self.dp, self.bot, self.recorder = dp, bot, recorder
        self.counter = 0

    def state(self, tg):
        return self.dp.fsm.get_context(bot=self.bot, chat_id=tg, user_id=tg)

    async def send(self, tg=1001, text=None, callback=None, **extra):
        self.counter += 1
        user = {'id': tg, 'is_bot': False, 'first_name': 'Employee'}
        message = {'message_id': extra.pop('message_id', self.counter), 'date': datetime.now(timezone.utc),
                   'chat': {'id': tg, 'type': 'private'}, 'from_user': user, **extra}
        if callback is not None:
            payload = {'callback_query': {'id': str(self.counter), 'from_user': user,
                       'chat_instance': 'audit', 'data': callback, 'message': message}}
        else:
            message['text'] = text
            if text and text.startswith('/start'):
                message['entities'] = [{'type': 'bot_command', 'offset': 0, 'length': 6}]
            payload = {'message': message}
        before = len(self.recorder.calls)
        await self.dp.feed_update(self.bot, Update(update_id=self.counter, **payload))
        return self.recorder.calls[before:]

    def callbacks(self, prefix):
        for call in reversed(self.recorder.calls):
            markup = getattr(call, 'reply_markup', None)
            if markup and hasattr(markup, 'inline_keyboard'):
                values = [b.callback_data for row in markup.inline_keyboard for b in row
                          if (b.callback_data or '').startswith(prefix)]
                if values:
                    return values
        return []


def make_harness():
    # Routers are module singletons. Reimport only the route definitions for a new dispatcher.
    for name in ('app.bot.handlers.user', 'app.bot.handlers.admin.panel', 'app.bot.handlers.admin.owner'):
        importlib.reload(importlib.import_module(name))
    main = importlib.reload(importlib.import_module('app.main'))
    recorder = TelegramRecorder()
    from app.bot.middlewares.outgoing import TelegramLimitsMiddleware
    recorder.middleware(TelegramLimitsMiddleware())
    return BotHarness(main.create_dispatcher(), Bot('123456:TEST', session=recorder), recorder)
