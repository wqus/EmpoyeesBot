from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_fsm_event_isolation_enabled():
    src = text("app/main.py")
    assert "SimpleEventIsolation" in src
    assert "events_isolation=SimpleEventIsolation()" in src


def test_exam_bank_uses_only_active_lessons():
    src = text("app/repositories/core.py")
    assert "join(Lesson, Lesson.id == ExamQuestion.lesson_id)" in src
    assert "Lesson.is_active.is_(True)" in src


def test_exam_history_is_real_database_pagination_not_500_cap():
    service = text("app/services/admin_crud.py")
    panel = text("app/bot/handlers/admin/panel.py")
    assert "async def exam_history(self, limit=50, offset=0)" in service
    assert ".offset(offset)" in service
    assert "exam_history_count" in service
    assert "limit=500" not in panel


def test_category_with_materials_is_not_cascade_deleted_from_ui():
    src = text("app/services/admin_crud.py")
    assert "Сначала удалите материалы из категории" in src


def test_user_flow_state_lock_covers_registration_test_and_admin_states():
    src = text("app/bot/middlewares/state_lock.py")
    assert "class UserFlowStateLockMiddleware" in src
    assert 'group == "LessonTest"' in src
    assert 'group == "Registration"' in src
    assert '"StudioAdminState"' in src


def test_lesson_test_has_explicit_cancel_and_finish_error_clears_state():
    src = text("app/bot/handlers/user.py")
    assert "callback_data='test:cancel'" in src
    assert "async def test_cancel" in src
    assert "Тест остановлен из-за изменения настроек" in src


def test_audit_log_requires_successful_flush():
    src = text("app/bot/middlewares/database.py")
    assert "did_flush" in src
    assert 'if action and s.sync_session.info.get("did_flush")' in src
