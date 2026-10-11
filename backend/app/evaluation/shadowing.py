"""Review read-aloud: compares what the user said with a known practice sentence.

Here, unlike free conversation, a reference sentence exists, so missing and extra words
can be shown (docs/design.md P2). Words the recognizer was unsure of are marked as
"unclear" instead of "missing", so recognition errors are not blamed on the user.
"""

import re
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel

from app.ai.alignment.ctc import NUMBER_WORDS
from app.ai.types import WordInfo

WordStatus = Literal["ok", "missing", "extra", "unclear"]


class ShadowWord(BaseModel):
    word: str
    status: WordStatus


class ShadowResult(BaseModel):
    reference: str
    heard: str
    words: list[ShadowWord]  # reference order, with extra words where they were said
    missing: list[str]
    extra: list[str]
    matched_ratio: float  # share of reference words that were heard


def _norm(word: str) -> str:
    w = re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'")).strip("'")
    return NUMBER_WORDS.get(w, w)


def _tokens(text: str) -> list[str]:
    return [w for w in text.split() if _norm(w)]


def compare(
    reference: str,
    heard: str,
    heard_words: list[WordInfo] | None = None,
    *,
    low_confidence: float = 0.6,
) -> ShadowResult:
    ref, hyp = _tokens(reference), _tokens(heard)
    unsure = {
        _norm(w.word)
        for w in heard_words or []
        if w.confidence is not None and w.confidence < low_confidence
    }
    matcher = SequenceMatcher(a=[_norm(w) for w in ref], b=[_norm(w) for w in hyp], autojunk=False)
    words: list[ShadowWord] = []
    missing: list[str] = []
    extra: list[str] = []
    matched = 0
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            matched += i2 - i1
            words += [ShadowWord(word=w, status="ok") for w in ref[i1:i2]]
            continue
        heard_here = hyp[j1:j2]
        # A substitution where the recognizer itself was unsure: don't call it a mistake.
        unclear = op == "replace" and any(_norm(w) in unsure for w in heard_here)
        for w in ref[i1:i2]:
            words.append(ShadowWord(word=w, status="unclear" if unclear else "missing"))
            if not unclear:
                missing.append(w)
        if not unclear:
            for w in heard_here:
                words.append(ShadowWord(word=w, status="extra"))
                extra.append(w)
    return ShadowResult(
        reference=reference,
        heard=heard,
        words=words,
        missing=missing,
        extra=extra,
        matched_ratio=round(matched / len(ref), 3) if ref else 0.0,
    )
