from app.ai.llm.mock import MockLLM
from app.scenes.director import Director
from app.scenes.llm_assist import LLMAssist

EMPTY = {
    "drink": None,
    "size": None,
    "temperature": None,
    "milk": None,
    "extra_shots": None,
    "requested_item_not_on_menu": None,
    "intent": "other",
}


def _assist(scene, extractor, *responses):
    return LLMAssist(scene, extractor, MockLLM([{**EMPTY, **r} for r in responses]))


def test_values_are_mapped_to_menu_ids(scene, extractor):
    ext = _assist(scene, extractor).to_extraction(
        {**EMPTY, "drink": "Hot Cocoa", "size": "big", "milk": "oat milk", "extra_shots": 1}
    )
    assert ext.slots == {"drink": "hot_chocolate", "size": "large", "milk": "oat", "extra_shots": 1}
    assert ext.source == "llm"


def test_invented_drink_becomes_unavailable_item(scene, extractor):
    ext = _assist(scene, extractor).to_extraction({**EMPTY, "drink": "matcha latte"})
    assert "drink" not in ext.slots
    assert ext.unknown_item == "matcha latte"


def test_off_menu_request_field(scene, extractor):
    ext = _assist(scene, extractor).to_extraction(
        {**EMPTY, "requested_item_not_on_menu": "Blueberry Muffin"}
    )
    assert ext.unknown_item == "blueberry muffin"


def test_out_of_range_values_are_ignored(scene, extractor):
    ext = _assist(scene, extractor).to_extraction(
        {**EMPTY, "size": "venti", "temperature": "lukewarm", "extra_shots": 9}
    )
    assert ext.slots == {}


def test_non_english_is_not_sent_to_llm(scene, extractor):
    assist = _assist(scene, extractor, {"drink": "latte"})
    assert assist("라떼 주세요") is None
    assert assist.calls == 0


def test_director_uses_assist_only_when_rules_find_nothing(scene, extractor):
    assist = _assist(scene, extractor, {"drink": "hot chocolate", "intent": "order"})
    director = Director(scene, extractor, assist)
    director.start()
    turn = director.handle("Something chocolatey for me.")
    assert turn.slots["drink"] == "hot_chocolate"
    assert turn.extraction.source == "llm"
    director.handle("Large please.")
    assert assist.calls == 1


def test_assist_returning_nothing_keeps_clarify(scene, extractor):
    director = Director(scene, extractor, _assist(scene, extractor, {"intent": "question"}))
    director.start()
    assert director.handle("What's good here?").action == "clarify"
