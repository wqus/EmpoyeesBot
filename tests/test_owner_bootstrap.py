from pathlib import Path


def test_owner_start_bypasses_employee_registration():
    source = Path("app/bot/handlers/user.py").read_text(encoding="utf-8")
    owner_check = "if m.from_user.id == settings.owner_telegram_id:"
    user_lookup = "u = await UserRepository(session).by_tg(m.from_user.id)"
    assert owner_check in source
    assert source.index(owner_check) < source.index(user_lookup, source.index("async def start"))
    assert "admin_panel_keyboard(owner=True)" in source


def test_owner_panel_contains_bootstrap_studio_management():
    source = Path("app/bot/handlers/admin/panel.py").read_text(encoding="utf-8")
    assert "def admin_panel_keyboard" in source
    assert "callback_data='admin:studios'" in source
    assert "callback_data='owner:admins'" in source
