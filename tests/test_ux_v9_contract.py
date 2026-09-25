from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def test_studio_delete_is_available_and_safe():
    panel=(ROOT/'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
    service=(ROOT/'app/services/admin_crud.py').read_text(encoding='utf-8')
    assert 'Удалить студию' in panel and 'delete_studio' in service
    assert 'Чтобы не потерять историю обучения' in service

def test_numeric_answer_ux():
    user=(ROOT/'app/bot/handlers/user.py').read_text(encoding='utf-8')
    assert user.count('Выберите номер ответа:') >= 2
    assert 'split_number_buttons' in user

def test_lesson_completion_messages():
    user=(ROOT/'app/bot/handlers/user.py').read_text(encoding='utf-8')
    assert 'Вы прошли уровень' in user and 'Теперь вам доступен урок' in user
    assert 'Теперь вам доступен итоговый экзамен' in user

def test_course_is_self_practice():
    course=json.loads((ROOT/'app/content/oasis_course.json').read_text(encoding='utf-8'))
    assert len(course)==10
    for item in course:
        assert 'Самопроверка' in item['content']
        assert 'Ничего отправлять в чат не нужно' in item['content']
        assert '🎯 Практическое задание' not in item['content']
    assert 'После прохождения теста:' not in course[0]['content']
    assert 'Переходим к Уроку 2' not in course[0]['content']

def test_admin_media_management():
    panel=(ROOT/'app/bot/handlers/admin/panel.py').read_text(encoding='utf-8')
    service=(ROOT/'app/services/admin_crud.py').read_text(encoding='utf-8')
    assert 'Изменить подпись' in panel and 'Заменить файл' in panel
    assert 'async def lesson_content_caption' in panel and 'async def lesson_content_replace_value' in panel
    assert 'edit_lesson_media_caption' in service and 'replace_lesson_media' in service

def test_v9_migration_chain():
    m=(ROOT/'alembic/versions/0005_course_ux.py').read_text(encoding='utf-8')
    assert "revision = '0005_course_ux'" in m and "down_revision = '0004_admin_actions'" in m
