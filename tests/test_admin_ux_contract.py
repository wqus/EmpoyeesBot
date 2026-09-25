from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / 'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
COMMON = (ROOT / 'app/bot/keyboards/common.py').read_text(encoding='utf-8')
MIDDLEWARE = (ROOT / 'app/bot/middlewares/state_lock.py').read_text(encoding='utf-8')
STATES = (ROOT / 'app/bot/states/admin.py').read_text(encoding='utf-8')


def test_admin_ui_has_no_decorative_emoji():
    banned = ['🙈', '👁', '🟢', '⚪', '👤', '📊', '📚', '📖', '📎', '🗂', '⬆', '⬇', '👑', '➕', '❌', '✅', '🧩', '❓']
    for token in banned:
        assert token not in PANEL
        assert token not in COMMON


def test_admin_fsm_has_cancel_and_lock():
    assert 'Отменить и вернуться' in PANEL
    assert 'fsm:cancel' in PANEL
    assert 'await state.clear()' in PANEL
    assert 'Сначала завершите текущее действие' in MIDDLEWARE


def test_media_uploads_use_real_states():
    assert 'add_media = State()' in STATES
    assert 'LessonAdminState.add_media' in PANEL
    assert 'MaterialAdminState.add_media' in PANEL


def test_buttons_use_full_move_names():
    assert 'Переместить выше' in PANEL
    assert 'Переместить ниже' in PANEL
    assert "text='⬆️'" not in PANEL
    assert "text='⬇️'" not in PANEL
