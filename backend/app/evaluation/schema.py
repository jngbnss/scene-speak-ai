from typing import Literal

from pydantic import BaseModel, Field

MAX_ITEMS = 5


class GrammarError(BaseModel):
    original: str = Field(min_length=1)
    corrected: str = Field(min_length=1)
    type: str = Field(min_length=1)
    explanation_ko: str


class UnnaturalExpression(BaseModel):
    original: str = Field(min_length=1)
    better: str = Field(min_length=1)
    reason_ko: str


class LineCheck(BaseModel):
    """The LLM's verdict on one customer line. It must decide grammar_ok for every line."""

    line: str
    grammar_ok: bool
    corrected: str = ""
    error_type: str = ""
    explanation_ko: str = ""
    more_natural: str = ""
    reason_ko: str = ""


class LLMFeedback(BaseModel):
    """What the LLM is asked to return. Everything else is computed, not generated."""

    lines: list[LineCheck]
    recommended_sentences: list[str]
    review_items: list[str]
    summary: str


class UncertainSpan(BaseModel):
    utterance_seq: int
    word: str
    confidence: float
    start: float | None = None
    end: float | None = None


class SpeechWord(BaseModel):
    word: str
    start: float
    end: float
    pause_before_ms: int = 0
    uncertain: bool = False


class ListenSegment(BaseModel):
    """A stretch of the user's recording worth replaying (seconds from the line start)."""

    start: float
    end: float
    reasons: list[Literal["pause", "uncertain"]]
    text: str


class LineSpeech(BaseModel):
    """Post-session timing hints for one spoken line. Describes timing, never a score."""

    utterance_seq: int
    text: str
    duration_s: float
    words: list[SpeechWord]
    long_pauses_ms: list[int] = []
    segments: list[ListenSegment] = []
    # "wav2vec2-..." when forced alignment ran, "asr" when only recognizer timings were used.
    timing_source: str


class Feedback(BaseModel):
    task_success: bool
    grammar_errors: list[GrammarError] = []
    unnatural_expressions: list[UnnaturalExpression] = []
    missed_information: list[str] = []
    recommended_sentences: list[str] = []
    review_items: list[str] = []
    summary: str = ""
    uncertain_spans: list[UncertainSpan] = []
    speech: list[LineSpeech] = []
    source: Literal["llm", "llm_retry", "default"] = "default"
    model_id: str | None = None
    # Items the evaluator removed and why ("not in transcript", "low ASR confidence").
    dropped: list[str] = []


_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}

# Hand-written (no $defs) so Ollama's grammar conversion handles it.
# Per-line checks force a grammar decision on every line. With two free lists
# (grammar_errors / unnatural_expressions) the model often filed grammar mistakes as
# "unnatural" (EXP-FB-001).
LLM_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line": _STR,
                    "grammar_ok": {"type": "boolean"},
                    "corrected": _STR,
                    "error_type": _STR,
                    "explanation_ko": _STR,
                    "more_natural": _STR,
                    "reason_ko": _STR,
                },
                "required": [
                    "line",
                    "grammar_ok",
                    "corrected",
                    "error_type",
                    "explanation_ko",
                    "more_natural",
                    "reason_ko",
                ],
            },
        },
        "recommended_sentences": _STR_LIST,
        "review_items": _STR_LIST,
        "summary": _STR,
    },
    "required": ["lines", "recommended_sentences", "review_items", "summary"],
}
