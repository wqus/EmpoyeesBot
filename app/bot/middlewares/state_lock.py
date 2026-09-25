from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class StateLockMiddleware(BaseMiddleware):
    """Blocks unrelated inline actions while an admin FSM operation is active."""

    async def __call__(self, handler, event, data):
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        state = data.get("state")
        current = await state.get_state() if state else None
        callback = event.data or ""
        allowed = callback.startswith("fsm:cancel") or (current and current.endswith(":choose_lesson") and callback.startswith("admin:exam:lesson:"))
        if current and not allowed:
            await event.answer(
                "Сначала завершите текущее действие или нажмите «Отменить и вернуться».",
                show_alert=True,
            )
            return None
        return await handler(event, data)


class UserFlowStateLockMiddleware(BaseMiddleware):
    """Prevents menu/old-button interleaving while a user/admin FSM flow is active."""

    async def __call__(self, handler, event, data):
        state = data.get("state")
        current = await state.get_state() if state else None
        if not current:
            return await handler(event, data)

        callback = (event.data or "") if isinstance(event, CallbackQuery) else None
        group = current.split(":", 1)[0]
        if isinstance(event, Message) and (event.text or '').split(maxsplit=1)[0:1] == ['/start'] and group in {'Registration', 'LessonTest'}:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if group == "Registration" and current.endswith(":studio"):
                if callback.startswith("reg:"):
                    return await handler(event, data)
                await event.answer("Сначала выберите студию.", show_alert=True)
                return None
            if group == "LessonTest":
                if callback.startswith("test:answer:") or callback == "test:cancel":
                    return await handler(event, data)
                await event.answer("Сначала завершите текущий тест или отмените его.", show_alert=True)
                return None
            if group in {"StudioAdminState", "LessonAdminState", "ExamAdminState", "MaterialAdminState"}:
                if callback.startswith("fsm:cancel") or (current.endswith(":choose_lesson") and callback.startswith("admin:exam:lesson:")):
                    return await handler(event, data)
                await event.answer("Сначала завершите текущее действие или нажмите «Отменить и вернуться».", show_alert=True)
                return None

        # Registration.name is itself a message-input state and must receive text.
        if group == "Registration" and current.endswith(":name"):
            return await handler(event, data)
        if group == "Registration" and current.endswith(":studio"):
            if isinstance(event, Message):
                await event.answer("Выберите студию кнопкой выше.")
                return None
        if group == "LessonTest" and isinstance(event, Message):
            await event.answer("Ответьте на текущий вопрос кнопкой или отмените тест.")
            return None
        if group in {"StudioAdminState", "LessonAdminState", "ExamAdminState", "MaterialAdminState"} and isinstance(event, Message):
            # State-specific admin handlers are selected before this middleware on their router.
            # If execution reached a user handler, it is unrelated input and must be blocked.
            await event.answer("Сначала завершите текущее действие или нажмите «Отменить и вернуться».")
            return None

        return await handler(event, data)
