from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_latest_migration_reasserts_nullable_owner_invite_creator():
    text = (ROOT / "alembic/versions/0003_invite_nullable.py").read_text(encoding="utf-8")
    assert '"admin_invites"' in text
    assert '"created_by_user_id"' in text
    assert "nullable=True" in text


def test_owner_invite_model_and_service_allow_no_employee_row():
    model = (ROOT / "app/database/models/admin.py").read_text(encoding="utf-8")
    service = (ROOT / "app/services/admin.py").read_text(encoding="utf-8")
    owner = (ROOT / "app/bot/handlers/admin/owner.py").read_text(encoding="utf-8")
    assert "Mapped[int | None]" in model
    assert "creator: int | None = None" in service
    assert "u.id if u else None" in owner
