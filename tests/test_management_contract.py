from app.services.admin_crud import AdminCrudService

def test_ops():
    assert {'user_results', 'exam_history', 'rename_lesson', 'move_lesson', 'delete_lesson', 'edit_exam_text', 'edit_exam_options', 'change_exam_lesson', 'delete_exam_question', 'edit_material_title', 'edit_material_content', 'move_material', 'delete_material'} <= set(dir(AdminCrudService))
