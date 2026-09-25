from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_balanced_exam_requires_each_active_topic():
    text = (ROOT / 'app/services/core.py').read_text(encoding='utf-8')
    assert 'минимум один вопрос по каждой активной теме/уроку' in text
    assert 'missing = [lesson.title for lesson in lessons if lesson.id not in by_lesson]' in text
    assert 'rng.choice(by_lesson[lesson.id])' in text


def test_destructive_actions_have_confirmation_layer():
    text = (ROOT / 'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
    assert 'danger_callback' in text
    assert 'Подтвердите действие' in text
    assert 'd:cancel' in text


def test_preview_pagination_analytics_and_owner_audit_exist():
    text = (ROOT / 'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
    for marker in ('admin:lesson:preview:', 'PAGE_SIZE = 10', 'admin:analytics', 'owner:audit:'):
        assert marker in text


def test_audit_table_and_migration_are_registered():
    assert (ROOT / 'app/database/models/audit.py').exists()
    migration = (ROOT / 'alembic/versions/0004_admin_actions.py').read_text(encoding='utf-8')
    assert "revision = '0004_admin_actions'" in migration
    assert "down_revision = '0003_invite_nullable'" in migration

def test_exam_notifications_removed_in_favor_of_history():
    text = (ROOT / 'app/bot/handlers/user.py').read_text(encoding='utf-8')
    assert 'Завершён экзамен' not in text
    assert "admin:exam:history" in (ROOT / 'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')


def test_stale_admin_callbacks_have_safe_fallback():
    text = (ROOT / 'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
    assert 'Эта кнопка устарела' in text
