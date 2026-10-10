import pytest

from app.ai.types import WordInfo
from app.evaluation.schema import Feedback, GrammarError, UnnaturalExpression


def _feedback(error_type="article") -> Feedback:
    return Feedback(
        task_success=True,
        grammar_errors=[
            GrammarError(
                original="I want hot latte.",
                corrected="I want a hot latte.",
                type=error_type,
                explanation_ko="",
            )
        ],
        unnatural_expressions=[
            UnnaturalExpression(original="I want", better="Can I get", reason_ko="")
        ],
        review_items=["Can I get a hot latte?"],
        source="llm",
    )


def _session(repo, sid="s1", nickname="mina"):
    uid = repo.get_or_create_user(nickname)
    repo.create_session(sid, uid, "new-york-cafe")
    return uid


def test_users_are_reused_by_nickname(repo):
    assert repo.get_or_create_user("mina") == repo.get_or_create_user("mina")
    assert repo.get_or_create_user("") == repo.get_or_create_user("guest")


def test_bad_nickname(repo):
    with pytest.raises(ValueError):
        repo.get_or_create_user("<script>")


def test_fix_keeps_raw_recognition(repo):
    _session(repo)
    words = [WordInfo(word="a", start=0, end=0.1, confidence=0.4)]
    repo.add_utterance("s1", 1, "user", "I want a oat late", words)
    assert repo.fix_utterance("s1", 1, "I want an oat latte")
    assert repo.user_lines("s1") == [(1, "I want an oat latte", [])]
    assert not repo.fix_utterance("s1", 9, "nope")


def test_transcript_order(repo):
    _session(repo)
    repo.add_utterance("s1", 1, "npc", "Hi")
    repo.add_utterance("s1", 1, "user", "Latte")
    repo.add_utterance("s1", 2, "npc", "Size?")
    assert repo.transcript("s1") == [("npc", "Hi"), ("user", "Latte"), ("npc", "Size?")]


def test_feedback_review_and_repeated_errors(repo):
    uid = _session(repo, "s1")
    repo.create_session("s2", uid, "new-york-cafe")
    repo.finish_session("s1", True, "completed")
    repo.finish_session("s2", False, "user_ended")
    repo.save_feedback("s1", _feedback())
    repo.save_feedback("s2", _feedback())

    assert repo.get_feedback("s1").grammar_errors[0].type == "article"
    assert repo.get_feedback("nope") is None

    review = repo.review(uid)
    assert review["nickname"] == "mina"
    assert review["review_items"] == [{"sentence": "Can I get a hot latte?", "times": 2}]
    assert review["repeated_errors"][0]["error_type"] == "article"
    assert review["repeated_errors"][0]["count"] == 2
    assert len(review["sessions"]) == 2
    assert repo.repeated_error_types(uid) == [("article", 2)]


def test_review_unknown_user(repo):
    with pytest.raises(KeyError):
        repo.review(999)
