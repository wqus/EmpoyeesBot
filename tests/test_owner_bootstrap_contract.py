from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(path): return (ROOT / path).read_text(encoding="utf-8")
def test_owner_has_persistent_menu_button():
    common=read("app/bot/keyboards/common.py"); user=read("app/bot/handlers/user.py")
    assert "⚙️ Меню владельца" in common and "is_persistent=True" in common and "reply_markup=owner_menu()" in user
def test_owner_invite_does_not_require_employee_registration():
    owner=read("app/bot/handlers/admin/owner.py"); model=read("app/database/models/admin.py")
    assert "u.id if u else None" in owner and "created_by_user_id: Mapped[int | None]" in model and "Сначала зарегистрируйтесь" not in owner
def test_owner_callbacks_are_state_locked():
    assert "router.callback_query.middleware(StateLockMiddleware())" in read("app/bot/handlers/admin/owner.py")
def test_admin_menu_does_not_clear_active_state():
    panel=read("app/bot/handlers/admin/panel.py")
    assert "current = await state.get_state()" in panel and "Сначала завершите текущее действие или отмените его." in panel
def test_media_handler_is_scoped_to_media_states():
    panel=read("app/bot/handlers/admin/panel.py")
    assert "@router.message(LessonAdminState.add_media, F.photo | F.video | F.document)" in panel
    assert "@router.message(MaterialAdminState.add_media, F.photo | F.video | F.document)" in panel
    assert "async def invalid_media_input" in panel
