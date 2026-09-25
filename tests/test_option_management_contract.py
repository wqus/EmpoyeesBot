from pathlib import Path

def test_individual_option_management_exists():
    root = Path(__file__).resolve().parents[1]
    service = (root / "app/services/admin_crud.py").read_text(encoding="utf-8")
    panel = (root / "app/bot/handlers/admin/panel.py").read_text(encoding="utf-8")
    for name in ("edit_lesson_option_text", "set_lesson_correct_option", "delete_lesson_option", "edit_exam_option_text", "set_exam_correct_option", "delete_exam_option"):
        assert f"def {name}" in service
    assert "Варианты ответа" in panel
    assert "Сделать правильным" in panel
    assert "Удалить вариант" in panel

def test_option_delete_safety_rules_present():
    text = (Path(__file__).resolve().parents[1] / "app/services/admin_crud.py").read_text(encoding="utf-8")
    assert "минимум два варианта" in text
    assert "Сначала назначьте правильным другой вариант" in text
