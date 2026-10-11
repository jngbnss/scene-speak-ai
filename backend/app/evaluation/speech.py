"""Post-session speech hints: long pauses, uncertain words, segments worth replaying.

Runs after the scene ends. Free conversation has no reference sentence, so this module
only describes *timing* (where the user paused, which words the recognizer was unsure
of). It never claims a word was missing or mispronounced (docs/design.md P2).
"""

import logging
import re

from app.ai.types import AdapterError, AlignerAdapter, AudioInput, WordInfo
from app.evaluation.schema import LineSpeech, ListenSegment, SpeechWord

log = logging.getLogger(__name__)

PAD_S = 0.3  # context around a replay segment
MERGE_GAP_S = 0.2


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'"))


def _asr_timings(words: list[WordInfo]) -> list[SpeechWord]:
    out: list[SpeechWord] = []
    for w in words:
        if not _norm(w.word):
            continue
        pause = int(round((w.start - out[-1].end) * 1000)) if out else 0
        out.append(SpeechWord(word=w.word.strip(), start=w.start, end=w.end, pause_before_ms=pause))
    return out


def _mark_uncertain(words: list[SpeechWord], asr_words: list[WordInfo], threshold: float) -> None:
    """Copies low ASR confidence onto the matching timed words (same order, same spelling)."""
    low = [
        _norm(w.word)
        for w in asr_words
        if _norm(w.word) and w.confidence is not None and w.confidence < threshold
    ]
    i = 0
    for word in words:
        if i < len(low) and _norm(word.word) == low[i]:
            word.uncertain = True
            i += 1


def _segments(
    words: list[SpeechWord], duration_s: float, long_pause_ms: int
) -> list[ListenSegment]:
    raw: list[tuple[float, float, str]] = []
    for i, w in enumerate(words):
        if i and w.pause_before_ms >= long_pause_ms:
            raw.append((words[i - 1].start, w.end, "pause"))
        if w.uncertain:
            raw.append((w.start - PAD_S, w.end + PAD_S, "uncertain"))
    merged: list[ListenSegment] = []
    for start, end, reason in sorted(raw):
        start, end = max(0.0, start), min(duration_s, end)
        if merged and start <= merged[-1].end + MERGE_GAP_S:
            last = merged[-1]
            last.end = max(last.end, end)
            if reason not in last.reasons:
                last.reasons.append(reason)
        else:
            merged.append(ListenSegment(start=start, end=end, reasons=[reason], text=""))
    for seg in merged:
        seg.start, seg.end = round(seg.start, 2), round(seg.end, 2)
        seg.text = " ".join(w.word for w in words if w.end > seg.start and w.start < seg.end)
    return merged


def analyze_line(
    seq: int,
    text: str,
    asr_words: list[WordInfo],
    audio: AudioInput,
    aligner: AlignerAdapter | None,
    *,
    low_confidence: float,
    long_pause_ms: int,
) -> LineSpeech:
    """Timing hints for one recorded line. Falls back to recognizer timings if alignment fails."""
    source = "asr"
    words: list[SpeechWord] = []
    if aligner is not None:
        try:
            aligned = aligner.align(audio, text)
            words = [
                SpeechWord(word=w.word, start=w.start, end=w.end, pause_before_ms=w.pause_before_ms)
                for w in aligned
            ]
            source = getattr(aligner, "model_id", "aligner")
        except AdapterError as exc:
            log.warning("alignment failed for line %d: %s", seq, exc)
    if not words:
        words, source = _asr_timings(asr_words), "asr"
    _mark_uncertain(words, asr_words, low_confidence)
    duration = audio.duration_ms / 1000
    return LineSpeech(
        utterance_seq=seq,
        text=text,
        duration_s=round(duration, 2),
        words=words,
        long_pauses_ms=[w.pause_before_ms for w in words[1:] if w.pause_before_ms >= long_pause_ms],
        segments=_segments(words, duration, long_pause_ms),
        timing_source=source,
    )
