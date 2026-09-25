from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_linear_head():
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    assert script.get_heads() == ["0006_runtime_integrity"]
    assert script.get_revision("0003_invite_nullable") is not None
    assert script.get_revision("0004_admin_actions").down_revision == "0003_invite_nullable"
    assert script.get_revision("0005_course_ux").down_revision == "0004_admin_actions"


def test_expected_migration_chain_present():
    root = Path(__file__).resolve().parents[1]
    versions = root / "alembic" / "versions"
    expected = {
        "0001_initial.py",
        "0002_owner_invite_without_user.py",
        "0003_invite_nullable.py",
        "0004_admin_actions.py",
        "0005_course_ux.py",
    }
    existing = {p.name for p in versions.glob("*.py") if p.name != "__init__.py"}
    assert expected <= existing
