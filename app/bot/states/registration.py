from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    name = State()
    studio = State()

class LessonTest(StatesGroup):
    answering = State()
