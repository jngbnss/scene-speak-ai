import pytest

from app.scenes.director import Director, InvalidTransitionError, SessionEndedError, human_join
from tests.conftest import load_dialogue_cases

CASES = load_dialogue_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_dialogue_case(scene, case):
    director = Director(scene)
    director.start()
    turn = None
    for i, step in enumerate(case["turns"]):
        turn = director.handle(step["user"])
        expect = step.get("expect")
        if not expect:
            continue
        where = f"turn {i + 1} ({step['user']!r})"
        if "action" in expect:
            assert turn.action == expect["action"], where
        if "phase" in expect:
            assert turn.phase == expect["phase"], where
        for slot, value in expect.get("slots", {}).items():
            assert turn.slots[slot] == value, f"{where} slot {slot}"
        if "item" in expect:
            assert turn.context["item"] == expect["item"], where
    final = case.get("final")
    if final:
        assert turn.phase == final["phase"]
        assert turn.success is final["success"]


def test_dialogue_cases_cover_every_director_action(scene):
    from app.scenes.validate import DIRECTOR_ACTIONS

    seen = {"greet"}
    for case in CASES:
        seen |= {s["expect"]["action"] for s in case["turns"] if "expect" in s}
    assert DIRECTOR_ACTIONS - seen == set()


def test_start_greets(scene):
    turn = Director(scene).start()
    assert (turn.action, turn.phase) == ("greet", "greeting")
    assert turn.missing_required == ["drink", "size", "temperature"]


def test_handle_after_end_raises(director):
    director.handle("cancel")
    with pytest.raises(SessionEndedError):
        director.handle("A latte")


def test_end_by_user_marks_failure(director):
    director.handle("I want a latte")
    turn = director.end_by_user()
    assert turn.ended and turn.success is False
    assert turn.end_reason == "user_ended"


def test_success_requires_confirmation(director):
    director.handle("A large hot latte with oat milk")
    turn = director.handle("Hmm.")
    assert turn.action == "confirm_order"
    assert not turn.ended


def test_order_summary(director):
    director.handle("A large hot latte with oat milk and two extra shots")
    assert director.order_summary() == "a large hot latte with oat milk and 2 extra shots"


def test_order_summary_uses_an_before_vowel(director):
    director.handle("A medium iced americano")
    director.state.slots["size"] = None
    assert director.order_summary() == "an iced Americano"


def test_invalid_transition_is_rejected(scene):
    director = Director(scene)
    director.start()
    director.state.phase = "completed"
    with pytest.raises(InvalidTransitionError):
        director._turn("ask_size", None, {})


def test_human_join():
    assert human_join(["a"]) == "a"
    assert human_join(["a", "b"], "and") == "a and b"
    assert human_join(["a", "b", "c"]) == "a, b, or c"
