from app.ai.llm.mock import MockLLM
from app.ai.types import WordInfo
from app.evaluation.evaluator import Evaluator, SessionSummary, UserLine
from app.scenes.loader import load_scene_file
from tests.conftest import SCENE_PATH

SCENE = load_scene_file(SCENE_PATH)


def check(line, corrected="", error_type="", natural="", ok=None):
    return {
        "line": line,
        "grammar_ok": (not corrected) if ok is None else ok,
        "corrected": corrected,
        "error_type": error_type,
        "explanation_ko": "설명" if corrected else "",
        "more_natural": natural,
        "reason_ko": "이유" if natural else "",
    }


GOOD = {
    "lines": [
        check("I want hot latte.", "I want a hot latte.", "Article"),
        check("Large, please. And can I have a oat milk?"),
        check("Yes, that's all."),
    ],
    "recommended_sentences": ["Can I get a large hot latte with oat milk?"],
    "review_items": ["Can I get a hot latte?"],
    "summary": "주문을 잘 마쳤어요.",
}


def _summary(user_lines_extra=(), **kw) -> SessionSummary:
    words = [
        WordInfo(word=w, start=i * 0.3, end=i * 0.3 + 0.3, confidence=c)
        for i, (w, c) in enumerate(
            [("Large,", 0.94), ("please.", 0.96), ("And", 0.9), ("can", 0.93), ("I", 0.97),
             ("have", 0.92), ("a", 0.91), ("oat", 0.48), ("milk?", 0.89)]
        )
    ]  # fmt: skip
    lines = [
        UserLine(1, "I want hot latte."),
        UserLine(2, "Large, please. And can I have a oat milk?", words),
        UserLine(3, "Yes, that's all."),
        *[UserLine(4 + i, t) for i, t in enumerate(user_lines_extra)],
    ]
    defaults = dict(
        transcript=[("npc", "Hi!")] + [("user", ln.text) for ln in lines],
        user_lines=lines,
        success=True,
        missing_required=[],
    )
    return SessionSummary(**{**defaults, **kw})


def _evaluate(*responses, **kw):
    llm = MockLLM(list(responses))
    return Evaluator(SCENE, llm).evaluate(_summary(**kw)), llm


def test_valid_feedback_is_kept():
    fb, _ = _evaluate(GOOD)
    assert fb.source == "llm"
    assert fb.task_success is True
    assert fb.grammar_errors[0].corrected == "I want a hot latte."
    assert fb.review_items == ["Can I get a hot latte?"]


def test_correction_of_text_the_user_never_said_is_dropped():
    fake = {**GOOD, "lines": [check("I goed home", "I went home", "tense")]}
    fb, _ = _evaluate(fake)
    assert fb.grammar_errors == []
    assert fb.dropped == ["not in transcript: I goed home"]


def test_grammar_mistake_wins_over_naturalness():
    both = {
        **GOOD,
        "lines": [
            check(
                "I want hot latte.",
                "I want a hot latte.",
                "article",
                natural="Can I get a hot latte?",
            )
        ],
    }
    fb, _ = _evaluate(both)
    assert [e.type for e in fb.grammar_errors] == ["article"]
    assert fb.unnatural_expressions == []


def test_correct_line_with_better_phrasing():
    fb, _ = _evaluate(
        {**GOOD, "lines": [check("Give me a latte.", natural="Can I get a latte?")]},
        user_lines_extra=["Give me a latte."],
    )
    assert fb.grammar_errors == []
    assert fb.unnatural_expressions[0].better == "Can I get a latte?"


def test_no_op_correction_is_ignored():
    fb, _ = _evaluate(
        {**GOOD, "lines": [check("I want hot latte.", "i want hot latte", "article")]}
    )
    assert fb.grammar_errors == []


def test_low_confidence_word_is_not_blamed_on_the_user():
    line = "Large, please. And can I have a oat milk?"
    fb, _ = _evaluate(
        {**GOOD, "lines": [check(line, "Large, please. And can I have oat milk?", "article")]}
    )
    assert fb.grammar_errors == []
    assert fb.dropped == [f"low ASR confidence: {line}"]
    assert [(u.utterance_seq, u.word, u.confidence) for u in fb.uncertain_spans] == [
        (2, "oat", 0.48)
    ]


def test_task_success_comes_from_director_not_llm():
    fb, _ = _evaluate(GOOD, success=False, missing_required=["size", "temperature"])
    assert fb.task_success is False
    assert fb.missed_information == ["크기", "온도"]


def test_invalid_output_is_retried_once():
    fb, llm = _evaluate({"summary": 3}, GOOD)
    assert fb.source == "llm_retry"
    assert "invalid" in llm.calls[1][-1].content


def test_two_invalid_outputs_give_safe_default():
    fb, _ = _evaluate({"oops": True}, {"lines": "none"})
    assert fb.source == "default"
    assert fb.task_success is True
    assert fb.grammar_errors == []
    assert fb.uncertain_spans  # still shown: computed, not generated


def test_review_items_fall_back_to_corrections():
    fb, _ = _evaluate(
        {
            **GOOD,
            "lines": [*GOOD["lines"], check("Give me a latte.", natural="Can I get a latte?")],
            "review_items": [],
        },
        user_lines_extra=["Give me a latte."],
    )
    assert fb.review_items == ["I want a hot latte.", "Can I get a latte?"]


def test_prompt_mentions_past_mistakes():
    _, llm = _evaluate(GOOD, past_error_types=["article"])
    assert "Mistakes this learner made before: article" in llm.calls[0][0].content


def test_short_spoken_answers_are_never_flagged():
    flag_short = {**GOOD, "lines": [check("Yes, that's all.", natural="Yes, that's everything.")]}
    fb, _ = _evaluate(flag_short)
    assert fb.unnatural_expressions == []
    assert fb.dropped == ["short answer: Yes, that's all."]


def test_short_answer_rule():
    ev = Evaluator(SCENE, MockLLM())
    assert ev.is_short_answer("Hot please.")
    assert ev.is_short_answer("Large, please.")
    assert not ev.is_short_answer("Two latte.")  # "two latte" is a real plural mistake
    assert not ev.is_short_answer("Can I has a latte?")


def test_advice_is_not_a_review_sentence():
    advice = {
        **GOOD,
        "review_items": ["Practice using 'a' before nouns.", "Can I get a hot latte?"],
        "recommended_sentences": ["Try polite forms like 'May I'.", "Could I have a latte?"],
    }
    fb, _ = _evaluate(advice)
    assert fb.review_items == ["Can I get a hot latte?"]
    assert fb.recommended_sentences == ["Could I have a latte?"]


def test_prompt_states_the_real_outcome():
    _, llm = _evaluate(GOOD, success=False, missing_required=["size"])
    assert "the order was NOT completed" in llm.calls[0][0].content
