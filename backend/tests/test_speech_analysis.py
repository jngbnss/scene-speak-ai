import numpy as np
import pytest

from app.ai.alignment.ctc import align_words, spoken_form, viterbi
from app.ai.alignment.mock import MockAligner
from app.ai.types import AdapterError, AlignedWord, AudioInput, WordInfo
from app.evaluation.shadowing import compare
from app.evaluation.speech import analyze_line

VOCAB = {"<pad>": 0, "|": 4, **{ch: 5 + i for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ'")}}


def emissions(frames: list[str]) -> np.ndarray:
    """Log probs where each frame strongly prefers one symbol ("-" = blank)."""
    probs = np.full((len(frames), len(VOCAB) + 4), 0.01)
    for t, sym in enumerate(frames):
        probs[t, 0 if sym == "-" else VOCAB[sym]] = 0.9
    probs /= probs.sum(axis=1, keepdims=True)
    return np.log(probs)


def test_spoken_form_handles_case_punctuation_and_numbers():
    assert spoken_form("Latte,") == "latte"
    assert spoken_form("I'm") == "i'm"
    assert spoken_form("2") == "two"
    assert spoken_form("—") == ""


def test_viterbi_follows_the_clear_path():
    log_probs = emissions(list("HH-I---"))
    path = viterbi(log_probs, [VOCAB["H"], VOCAB["I"]])
    assert path == [0, 0, -1, 1, -1, -1, -1]


def test_viterbi_needs_a_blank_between_repeated_letters():
    assert viterbi(emissions(list("LL")), [VOCAB["L"], VOCAB["L"]]) is None
    assert viterbi(emissions(list("L-L")), [VOCAB["L"], VOCAB["L"]]) is not None


def test_align_words_finds_the_silence_between_words():
    frames = list("HI") + ["-"] * 10 + list("|YO") + ["-"]
    spans = align_words(emissions(frames), ["Hi,", "yo!"], VOCAB)
    assert [(s.word, s.start_frame, s.end_frame) for s in spans] == [
        ("Hi,", 0, 2),
        ("yo!", 13, 15),
    ]
    assert all(0.7 < s.score <= 1 for s in spans)  # 0.9 / (0.9 + 35 * 0.01)


def test_align_words_skips_words_without_letters():
    spans = align_words(emissions(list("HI")), ["—", "hi"], VOCAB)
    assert [s.word for s in spans] == ["hi"]


def _audio(seconds: float) -> AudioInput:
    return AudioInput(pcm16=b"\x00\x01" * int(16000 * seconds))


class FixedAligner:
    model_id = "fixed"

    def __init__(self, words: list[AlignedWord]) -> None:
        self.words = words

    def align(self, audio, text):
        return self.words


def _aligned(*spec: tuple[str, float, float]) -> list[AlignedWord]:
    out: list[AlignedWord] = []
    for word, start, end in spec:
        pause = int(round((start - out[-1].end) * 1000)) if out else 0
        out.append(AlignedWord(word=word, start=start, end=end, pause_before_ms=pause))
    return out


def test_long_pause_becomes_a_replay_segment():
    aligner = FixedAligner(
        _aligned(("a", 0.1, 0.2), ("large", 0.25, 0.6), ("latte", 1.7, 2.1), ("please", 2.2, 2.6))
    )
    line = analyze_line(
        3, "a large latte please", [], _audio(3), aligner, low_confidence=0.6, long_pause_ms=800
    )
    assert line.timing_source == "fixed"
    assert line.long_pauses_ms == [1100]
    assert len(line.segments) == 1
    seg = line.segments[0]
    assert (seg.start, seg.end, seg.reasons, seg.text) == (0.25, 2.1, ["pause"], "large latte")


def test_uncertain_word_segment_is_padded_and_merged_with_a_nearby_pause():
    aligner = FixedAligner(_aligned(("oat", 0.1, 0.4), ("milk", 1.4, 1.7)))
    asr = [
        WordInfo(word="oat", start=0.1, end=0.4, confidence=0.3),
        WordInfo(word="milk", start=1.4, end=1.7, confidence=0.9),
    ]
    line = analyze_line(
        1, "oat milk", asr, _audio(2), aligner, low_confidence=0.6, long_pause_ms=800
    )
    assert [w.uncertain for w in line.words] == [True, False]
    assert len(line.segments) == 1
    assert line.segments[0].start == 0.0  # clamped at the line start
    assert set(line.segments[0].reasons) == {"pause", "uncertain"}


def test_short_pauses_give_no_segments():
    line = analyze_line(
        1, "hot latte please", [], _audio(1.5), MockAligner(), low_confidence=0.6, long_pause_ms=800
    )
    assert line.segments == [] and line.long_pauses_ms == []
    assert [w.word for w in line.words] == ["hot", "latte", "please"]


def test_failed_alignment_falls_back_to_recognizer_timings():
    class Broken:
        model_id = "broken"

        def align(self, audio, text):
            raise AdapterError("onnx error")

    asr = [
        WordInfo(word="hi", start=0.0, end=0.2, confidence=0.9),
        WordInfo(word="there", start=1.2, end=1.5, confidence=0.9),
    ]
    line = analyze_line(
        1, "hi there", asr, _audio(2), Broken(), low_confidence=0.6, long_pause_ms=800
    )
    assert line.timing_source == "asr"
    assert line.long_pauses_ms == [1000]


@pytest.mark.parametrize(
    ("heard", "missing", "extra"),
    [
        ("Can I get a large latte please", [], []),
        ("Can I get large latte", ["a", "please?"], []),
        ("Can I get a a large latte, please?", [], ["a"]),
        ("Can I have a large latte please", ["get"], ["have"]),
    ],
)
def test_shadowing_reports_missing_and_extra_words(heard, missing, extra):
    result = compare("Can I get a large latte, please?", heard)
    assert result.missing == missing
    assert result.extra == extra


def test_shadowing_does_not_blame_words_the_recognizer_was_unsure_of():
    words = [WordInfo(word=w, start=0, end=0, confidence=0.9) for w in "I want a".split()]
    words += [WordInfo(word="lot", start=0, end=0, confidence=0.3)]
    result = compare("I want a latte.", "I want a lot", words)
    assert result.missing == [] and result.extra == []
    assert [w.status for w in result.words] == ["ok", "ok", "ok", "unclear"]
    assert result.matched_ratio == 0.75


def test_shadowing_counts_numbers_as_words():
    assert compare("Two shots, please.", "2 shots please").missing == []
