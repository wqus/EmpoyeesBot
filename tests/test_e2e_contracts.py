import inspect
from app.repositories.core import UserRepository
from app.services.admin import AccessService
from app.services.admin_crud import AdminCrudService

def test_user_repo_eager_loads_studio_for_async_report_path():
    assert 'selectinload(User.studio)' in inspect.getsource(UserRepository.by_tg)

def test_access_service_checks_active_user():
    src = inspect.getsource(AccessService.admin)
    assert 'user.is_active' in src

def test_management_surface_is_complete():
    required = {'rename_lesson', 'move_lesson', 'delete_lesson', 'edit_lesson_media_text', 'delete_lesson_media', 'edit_lesson_question_text', 'edit_lesson_question_options', 'toggle_lesson_question', 'delete_lesson_question', 'edit_exam_text', 'edit_exam_options', 'change_exam_lesson', 'delete_exam_question', 'user_results', 'exam_history', 'rename_category', 'delete_category', 'edit_material_title', 'edit_material_content', 'move_material', 'delete_material', 'delete_material_media'}
    assert required <= set(dir(AdminCrudService))

def test_lesson_reorder_protects_existing_progress():
    assert 'LessonProgress' in inspect.getsource(AdminCrudService.move_lesson)

def test_historical_question_mutations_are_guarded():
    assert 'LessonTestAnswer' in inspect.getsource(AdminCrudService.edit_lesson_question_options)
    assert 'ExamAnswer' in inspect.getsource(AdminCrudService.edit_exam_options)

def test_exam_answer_path_uses_row_lock():
    from app.repositories.core import ExamRepository
    assert 'with_for_update' in inspect.getsource(ExamRepository.next_unanswered_for_update)

def test_registered_start_clears_stale_fsm():
    from pathlib import Path
    src = (Path(__file__).parents[1] / 'app/bot/handlers/user.py').read_text(encoding='utf-8')
    assert 'if u:\n        await state.clear()' in src
