from app.services.admin import ContentValidator

class O:

    def __init__(self, text, correct=False):
        self.text = text
        self.is_correct = correct

class Q:

    def __init__(self, text, options):
        self.text = text
        self.options = options

def test_valid_question():
    assert ContentValidator.question(Q('Q', [O('A', True), O('B')])) == []

def test_question_requires_exactly_one_correct():
    assert ContentValidator.question(Q('Q', [O('A', True), O('B', True)]))

def test_question_requires_two_options():
    assert ContentValidator.question(Q('Q', [O('A', True)]))
