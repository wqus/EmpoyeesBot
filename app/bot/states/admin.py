from aiogram.fsm.state import State, StatesGroup

class StudioAdminState(StatesGroup):
    create = State()
    rename = State()

class LessonAdminState(StatesGroup):
    create_title = State()
    edit_title = State()
    add_text = State()
    add_media = State()
    edit_text_block = State()
    edit_media_caption = State()
    replace_media = State()
    add_question_text = State()
    add_question_options = State()
    edit_question_text = State()
    edit_question_options = State()
    edit_option_text = State()

class ExamAdminState(StatesGroup):
    choose_lesson = State()
    question_text = State()
    question_options = State()
    edit_text = State()
    edit_options = State()
    edit_option_text = State()

class MaterialAdminState(StatesGroup):
    category_name = State()
    category_rename = State()
    material_title = State()
    material_content = State()
    add_media = State()
    edit_title = State()
    edit_content = State()
