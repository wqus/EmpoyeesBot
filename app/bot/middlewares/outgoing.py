from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import AnswerCallbackQuery, SendMessage
from app.utils.text import text_chunks


class TelegramLimitsMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        if isinstance(method, AnswerCallbackQuery) and method.text:
            method = method.model_copy(update={'text': next(text_chunks(method.text, 200))})
        if isinstance(method, SendMessage) and not method.entities:
            chunks = list(text_chunks(method.text, html_mode=method.parse_mode == 'HTML'))
            if len(chunks) > 1:
                for index, chunk in enumerate(chunks):
                    result = await make_request(bot, method.model_copy(update={
                        'text': chunk,
                        'reply_markup': method.reply_markup if index == len(chunks) - 1 else None,
                    }))
                return result
        return await make_request(bot, method)
