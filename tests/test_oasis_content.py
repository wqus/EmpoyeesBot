import json
from pathlib import Path
COURSE_PATH = Path(__file__).parents[1] / 'app' / 'content' / 'oasis_course.json'

def test_oasis_course_shape():
    course = json.loads(COURSE_PATH.read_text(encoding='utf-8'))
    assert len(course) == 10
    assert [x['position'] for x in course] == list(range(1, 11))
    assert sum((len(x['questions']) for x in course)) == 50
    for lesson in course:
        assert lesson['content'].strip()
        assert len(lesson['questions']) == 5
        for question in lesson['questions']:
            assert len(question['options']) == 4
            assert sum((bool(x['is_correct']) for x in question['options'])) == 1
