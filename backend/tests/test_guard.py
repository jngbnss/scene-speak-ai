import pytest

from app.scenes.guard import count_sentences


def test_clean_reply_passes(guard):
    assert guard.check("Sure! What size would you like?").ok


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        ("Sorry, we're out of that, but our maple latte is popular!", "off-menu item: maple latte"),
        ("How about a mocha?", "off-menu item: mocha"),
        ("That will be $5.", "forbidden pattern"),
        ("As an AI, I cannot drink coffee.", "forbidden pattern"),
        ("Good grammar there!", "forbidden pattern"),
        ("Sure. Okay. What size?", "more than 2 sentences"),
        ("   ", "empty reply"),
    ],
)
def test_violations(guard, text, violation):
    result = guard.check(text)
    assert not result.ok
    assert any(v.startswith(violation) for v in result.violations), result.violations


def test_allowed_mention_for_unavailable_item(guard):
    text = "Sorry, we don't have pumpkin spice latte. We have latte or Americano."
    assert not guard.check(text).ok
    assert guard.check(text, allowed_mentions=("pumpkin spice latte",)).ok


def test_count_sentences():
    assert count_sentences("Hi there! What can I get for you today?") == 2
    assert count_sentences("So that's a large latte. Is that everything?") == 2
    assert count_sentences("One sentence") == 1


@pytest.mark.parametrize(
    "text",
    [
        "Sorry, we only serve cold brew iced. Is that okay?",
        "Our cold brew comes iced. Enjoy your latte!",
    ],
)
def test_ordinary_barista_phrasing_passes(guard, text):
    assert guard.check(text).ok, guard.check(text).violations


def test_role_confusion_is_caught_but_barista_questions_pass(guard):
    assert not guard.check("Sorry, can I get a latte or an Americano?").ok
    assert guard.check("Hi! What can I get you today?").ok
    assert guard.check("What can I get for you?").ok
