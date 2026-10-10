import pytest

from app.scenes.extractor import tokenize


@pytest.mark.parametrize(
    ("text", "slots"),
    [
        ("I want hot latte.", {"drink": "latte", "temperature": "hot"}),
        ("Large, please. And can I have oat milk?", {"size": "large", "milk": "oat"}),
        ("Can I get a small hot chocolate?", {"drink": "hot_chocolate", "size": "small"}),
        ("A medium cold brew", {"drink": "cold_brew", "size": "medium"}),
        ("regular size with regular milk", {"size": "medium", "milk": "whole"}),
        ("a black coffee", {"drink": "americano"}),
        ("with an extra shot", {"extra_shots": 1}),
        ("with two extra shots", {"extra_shots": 2}),
        ("no extra shots", {"extra_shots": 0}),
        ("A latte, no, actually an americano.", {"drink": "americano"}),
        ("I’d like an iced latte", {"drink": "latte", "temperature": "iced"}),
    ],
)
def test_slots(extractor, text, slots):
    assert extractor.extract(text).slots == slots


def test_hot_chocolate_is_not_read_as_hot_temperature(extractor):
    assert "temperature" not in extractor.extract("hot chocolate please").slots


def test_unknown_modifier_marks_item_unavailable(extractor):
    ext = extractor.extract("Can I get a pumpkin spice latte?")
    assert ext.unknown_item == "pumpkin spice latte"
    assert "drink" not in ext.slots


def test_off_menu_term(extractor):
    assert extractor.extract("Do you have green tea?").unknown_item == "green tea"


def test_valid_drink_overrides_unknown_mention(extractor):
    ext = extractor.extract("No cappuccino? Then a latte.")
    assert ext.unknown_item is None
    assert ext.slots["drink"] == "latte"


@pytest.mark.parametrize(
    ("text", "intents"),
    [
        ("Yes, that's all.", {"confirm", "done"}),
        ("No, that's not right.", {"deny"}),
        ("No milk, please.", {"deny"}),
        ("Never mind, cancel my order.", {"cancel"}),
        ("I'm not sure what I want, okay", set()),
        ("Oh, okay. Iced is fine.", {"confirm"}),
    ],
)
def test_intents(extractor, text, intents):
    assert extractor.extract(text).intents == intents


def test_tokenize_keeps_punctuation_as_boundaries():
    assert [t.text for t in tokenize("Cold, brew!")] == ["cold", ",", "brew", "!"]


def test_punctuation_breaks_alias(extractor):
    assert extractor.extract("cold, brew").slots == {"temperature": "iced"}


def test_unknown_mentions_for_guard(extractor):
    assert extractor.unknown_mentions("Try our maple latte or a mocha!") == ["maple latte", "mocha"]
    assert (
        extractor.unknown_mentions("We have latte, Americano, cold brew, or hot chocolate.") == []
    )
