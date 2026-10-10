"""Learning Evaluator: post-session feedback on the user's English.

The LLM proposes corrections; this module decides what the user sees:
- ``task_success`` and ``missed_information`` come from the Director, never the LLM.
- Corrections must quote a real user line, or they are dropped.
- Corrections that touch a low-confidence ASR word are dropped and the word is shown
  as "uncertain" instead, so recognition errors are not blamed on the user.
- Invalid output is retried once, then replaced by a safe default.
"""

import logging
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.ai.types import AdapterError, ChatMessage, LLMAdapter, WordInfo
from app.evaluation.schema import (
    LLM_FEEDBACK_SCHEMA,
    MAX_ITEMS,
    Feedback,
    GrammarError,
    LLMFeedback,
    UncertainSpan,
    UnnaturalExpression,
)
from app.scenes.extractor import STOPWORDS
from app.scenes.models import Scene

log = logging.getLogger(__name__)

SLOT_NAMES_KO = {
    "drink": "음료",
    "size": "크기",
    "temperature": "온도",
    "milk": "우유",
    "extra_shots": "추가 샷",
}


@dataclass
class UserLine:
    seq: int
    text: str
    words: list[WordInfo] = field(default_factory=list)


@dataclass
class SessionSummary:
    """What the evaluator needs to know about a finished session."""

    transcript: list[tuple[str, str]]  # (speaker, text) in order
    user_lines: list[UserLine]
    success: bool
    missing_required: list[str]
    past_error_types: list[str] = field(default_factory=list)


def _norm_words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("’", "'")).split()


_ADVICE = re.compile(r"^(practice|try|use|remember|focus|avoid|don't|do not|make sure)\b", re.I)


def _sentences(items: list[str]) -> list[str]:
    """Practice sentences only: drops advice ("Practice using 'a'...") and duplicates."""
    return list(
        dict.fromkeys(x.strip() for x in items if x.strip() and not _ADVICE.match(x.strip()))
    )


def _changed(original: str, proposed: str) -> bool:
    """A correction that only changes punctuation or case is not a correction."""
    return bool(_norm_words(proposed)) and _norm_words(proposed) != _norm_words(original)


def _contains(haystack: str, needle: str) -> bool:
    h, n = _norm_words(haystack), _norm_words(needle)
    if not n:
        return False
    return any(h[i : i + len(n)] == n for i in range(len(h) - len(n) + 1))


SHORT_ANSWER_MAX_WORDS = 3


def scene_vocabulary(scene: Scene) -> set[str]:
    menu = scene.menu
    phrases = [a for d in menu.drinks for a in d.aliases]
    for options in (menu.sizes, menu.temperatures, menu.milks):
        phrases += [a for o in options for a in o.aliases]
    for name in ("cancel", "done", "deny", "confirm"):
        phrases += getattr(scene.intents, name)
    # Number words stay out: "Two latte." is a real plural mistake, not a short answer.
    return {w for p in phrases for w in _norm_words(p)} | (STOPWORDS - {"one", "two", "three"})


class Evaluator:
    def __init__(self, scene: Scene, llm: LLMAdapter, low_confidence: float = 0.6) -> None:
        self.scene = scene
        self.llm = llm
        self.low_confidence = low_confidence
        self._vocab = scene_vocabulary(scene)

    def is_short_answer(self, text: str) -> bool:
        """'Hot please.', 'Yes, that's all.': correct spoken answers the model tends to flag."""
        words = _norm_words(text)
        return len(words) <= SHORT_ANSWER_MAX_WORDS and all(w in self._vocab for w in words)

    def messages(self, s: SessionSummary) -> list[ChatMessage]:
        lines = "\n".join(
            f"{'CUSTOMER' if who == 'user' else 'BARISTA'}: {text}" for who, text in s.transcript
        )
        focus = ", ".join(self.scene.learning.feedback_focus)
        outcome = (
            "the order was completed"
            if s.success
            else "the order was NOT completed (cancelled or ended early)"
        )
        past = ", ".join(s.past_error_types) or "none"
        system = f"""You are a friendly English tutor for Korean adults learning travel English.
Review only the CUSTOMER lines of this café conversation.

Return one entry in "lines" for EVERY customer line, in order, copying it into "line".
For each line decide two things:

1. grammar_ok: would an English teacher mark the line wrong? Check a/an and missing
   articles ("I want hot latte" -> "a hot latte", "an latte" -> "a latte"), plurals
   ("two latte" -> "two lattes"), verb forms ("Can I has" -> "Can I have"), subject-verb
   agreement ("She want" -> "She wants"), word order, prepositions, tense.
   If wrong: grammar_ok=false, "corrected" = the fixed line, error_type = one of article,
   plural, verb_form, subject_verb_agreement, word_order, preposition, tense, and a Korean
   explanation_ko. If right: grammar_ok=true and leave those fields empty.
2. more_natural: only if the line is correct but sounds rude or unnatural in a café
   ("Give me a latte."), give a better line and a Korean reason_ko. Otherwise "".

Short spoken answers are correct and natural: "Hot.", "Medium.", "Large, please.", "Yes.",
"No, thanks." Mark them grammar_ok=true with more_natural "".

Other fields:
- recommended_sentences: up to 3 natural sentences the CUSTOMER (not the barista) could
  say next time to order the same thing.
- review_items: up to 3 English sentences the customer should practice saying out loud,
  usually the corrected versions of their own lines. Sentences only, never advice.
- explanation_ko, reason_ko and summary MUST be written in Korean (한국어), one sentence each.
- summary: say how the order went (outcome below) and the single most useful tip based on
  the mistakes you actually found. Do not mention mistakes that are not in your lists.

- If every line is correct and natural, say so in the summary.

Outcome of this conversation: {outcome}
Focus areas: {focus}. Mistakes this learner made before: {past}."""
        return [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=f"Conversation:\n{lines}"),
        ]

    def evaluate(self, s: SessionSummary) -> Feedback:
        messages = self.messages(s)
        for attempt in (1, 2):
            try:
                result = self.llm.generate(
                    messages, json_schema=LLM_FEEDBACK_SCHEMA, max_tokens=1500, temperature=0.2
                )
                parsed = LLMFeedback.model_validate(result.parsed or {})
            except (AdapterError, ValidationError) as exc:
                log.warning("feedback attempt %d failed: %s", attempt, str(exc)[:300])
                messages = [
                    *messages,
                    ChatMessage(
                        role="system",
                        content="Your last answer was invalid. Return JSON that matches the "
                        "schema exactly.",
                    ),
                ]
                continue
            return self._finalize(
                s, parsed, "llm" if attempt == 1 else "llm_retry", result.model_id
            )
        return self.default(s)

    def default(self, s: SessionSummary) -> Feedback:
        feedback = Feedback(
            task_success=s.success,
            missed_information=self._missed(s),
            summary="이번 대화의 피드백을 만들지 못했어요. 대화 기록은 저장됐어요.",
            source="default",
        )
        feedback.uncertain_spans = self._uncertain(s)
        return feedback

    # ----- validation -------------------------------------------------------------------

    def _missed(self, s: SessionSummary) -> list[str]:
        if s.success:
            return []
        return [SLOT_NAMES_KO.get(slot, slot) for slot in s.missing_required]

    def _uncertain(self, s: SessionSummary) -> list[UncertainSpan]:
        return [
            UncertainSpan(
                utterance_seq=line.seq,
                word=w.word,
                confidence=w.confidence,
                start=w.start,
                end=w.end,
            )
            for line in s.user_lines
            for w in line.words
            if w.confidence is not None and w.confidence < self.low_confidence
        ]

    def _finalize(
        self, s: SessionSummary, parsed: LLMFeedback, source: str, model_id: str
    ) -> Feedback:
        uncertain = self._uncertain(s)
        uncertain_words = {(u.utterance_seq, u.word.lower().strip(".,!?")) for u in uncertain}
        dropped: list[str] = []

        def keep(original: str) -> bool:
            lines = [ln for ln in s.user_lines if _contains(ln.text, original)]
            if not lines:
                dropped.append(f"not in transcript: {original}")
                return False
            if self.is_short_answer(original):
                dropped.append(f"short answer: {original}")
                return False
            for ln in lines:
                touched = {(ln.seq, w) for w in _norm_words(original)}
                if touched & uncertain_words:
                    dropped.append(f"low ASR confidence: {original}")
                    return False
            return True

        grammar: list[GrammarError] = []
        unnatural: list[UnnaturalExpression] = []
        for check in parsed.lines:
            original = check.line.strip()
            if not check.grammar_ok and _changed(original, check.corrected):
                if keep(original):
                    grammar.append(
                        GrammarError(
                            original=original,
                            corrected=check.corrected.strip(),
                            type=check.error_type.strip().lower() or "grammar",
                            explanation_ko=check.explanation_ko.strip(),
                        )
                    )
            elif _changed(original, check.more_natural) and keep(original):
                unnatural.append(
                    UnnaturalExpression(
                        original=original,
                        better=check.more_natural.strip(),
                        reason_ko=check.reason_ko.strip(),
                    )
                )
        grammar, unnatural = grammar[:MAX_ITEMS], unnatural[:MAX_ITEMS]
        recommended = _sentences(parsed.recommended_sentences)
        review = _sentences(parsed.review_items)
        if not review:
            review = [e.corrected for e in grammar] + [e.better for e in unnatural]
            review = list(dict.fromkeys(review))
        return Feedback(
            task_success=s.success,
            grammar_errors=grammar,
            unnatural_expressions=unnatural,
            missed_information=self._missed(s),
            recommended_sentences=recommended[:3],
            review_items=review[:3],
            summary=parsed.summary.strip(),
            uncertain_spans=uncertain,
            source=source,  # type: ignore[arg-type]
            model_id=model_id,
            dropped=dropped,
        )
