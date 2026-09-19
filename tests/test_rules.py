import pytest
from app.services.core import LessonTestService, ExamService
from app.services.admin import ContentValidator
from app.core.exceptions import ContentValidationError

def test_lesson_thresholds():
    assert LessonTestService.required(1) == 1
    assert LessonTestService.required(5) == 4
    assert LessonTestService.required(6) == 5
    assert LessonTestService.required(10) == 8
    assert LessonTestService.required(12) == 10

def test_exam_constants():
    assert ExamService.COUNT == 30
    assert ExamService.PASS == 27

class O:

    def __init__(self, text, is_correct=False):
        self.text = text
        self.is_correct = is_correct

class Q:

    def __init__(self, text, options):
        self.text = text
        self.options = options

def test_question_validation():
    assert ContentValidator.question(Q('Q', [O('A', True), O('B')])) == []
    assert ContentValidator.question(Q('', [O('A'), O('B')]))
    assert ContentValidator.question(Q('Q', [O('A', True), O('B', True)]))
