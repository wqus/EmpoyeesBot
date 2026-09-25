from pathlib import Path


def test_result_service_weak_topics_is_always_counter():
    src = Path("app/services/core.py").read_text(encoding="utf-8")
    start = src.index("class ResultService:")
    block = src[start:]
    assert "weak = Counter()" in block
    assert "weak = []" not in block


def test_user_results_handler_can_call_most_common():
    src = Path("app/bot/handlers/user.py").read_text(encoding="utf-8")
    assert "weak.most_common()" in src
