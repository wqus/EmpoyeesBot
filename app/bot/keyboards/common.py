from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

def menu(admin=False):
    rows = [[KeyboardButton(text='Обучение'), KeyboardButton(text='Материалы')], [KeyboardButton(text='Экзамен'), KeyboardButton(text='Мой результат')]]
    if admin:
        rows.append([KeyboardButton(text='Админ-панель')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def studios(items):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.name, callback_data=f'reg:{x.id}')] for x in items])

def lessons(items):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{('Недоступно -' if p.status.value == 'locked' else 'Пройдено -' if p.status.value == 'passed' else 'Доступно -')} {p.lesson.title}", callback_data=f'lesson:{p.lesson_id}')] for p in items])

def options(prefix, q):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=o.text, callback_data=f'{prefix}:{q.id}:{o.id}')] for o in q.options])


def owner_menu():
    """Persistent owner-only entry point. Kept intentionally minimal."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⚙️ Меню владельца")]],
        resize_keyboard=True,
        is_persistent=True,
    )
