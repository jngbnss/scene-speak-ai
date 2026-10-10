"""FasterWhisperSTT logic with a fake faster_whisper module (no model download)."""

import sys
import types
from dataclasses import dataclass

import pytest

from app.ai.types import AudioInput


@dataclass
class FakeWord:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class FakeSegment:
    text: str
    words: list


class FakeModel:
    calls: list[dict] = []

    def __init__(self, name, device, compute_type):
        self.name = name

    def transcribe(self, samples, **kwargs):
        FakeModel.calls.append(kwargs)
        words = [FakeWord(" hot", 0.0, 0.3, 0.42), FakeWord(" latte", 0.3, 0.7, 0.97)]
        return iter([FakeSegment(" hot latte", words)]), types.SimpleNamespace(language="en")


@pytest.fixture
def stt_class(monkeypatch):
    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    FakeModel.calls = []
    from app.ai.stt.faster_whisper import FasterWhisperSTT

    return FasterWhisperSTT


TWO_SECONDS = AudioInput(pcm16=b"\x00\x01" * 32000, sample_rate=16000)


def test_words_and_confidence(stt_class):
    result = stt_class(device="cpu", compute_type="int8").transcribe(TWO_SECONDS)
    assert result.text == "hot latte"
    assert [(w.word, w.confidence) for w in result.words] == [("hot", 0.42), ("latte", 0.97)]
    assert result.audio_duration_ms == 2000


@pytest.mark.parametrize(
    ("mode", "key", "value"),
    [
        ("hotwords", "hotwords", "latte oat milk"),
        ("prompt", "initial_prompt", "A customer orders at a café: latte, oat milk."),
    ],
)
def test_context_modes(stt_class, mode, key, value):
    stt_class(device="cpu", context_mode=mode).transcribe(
        TWO_SECONDS, hotwords=["latte", "oat milk"]
    )
    assert FakeModel.calls[-1][key] == value


def test_no_context(stt_class):
    stt_class(device="cpu", context_mode="none").transcribe(TWO_SECONDS, hotwords=["latte"])
    assert "hotwords" not in FakeModel.calls[-1] and "initial_prompt" not in FakeModel.calls[-1]


def test_token_cap_is_off_by_default_and_follows_audio_length(stt_class):
    stt_class(device="cpu").transcribe(TWO_SECONDS)
    assert "max_new_tokens" not in FakeModel.calls[-1]
    capped = stt_class(device="cpu", cap_tokens=True)
    capped.transcribe(TWO_SECONDS)
    assert FakeModel.calls[-1]["max_new_tokens"] == 2 * 6 + 4
    capped.transcribe(AudioInput(pcm16=b"\x00\x00" * 1600))
    assert FakeModel.calls[-1]["max_new_tokens"] == 12  # minimum for very short clips


def test_resamples_to_16k(stt_class):
    one_second_48k = AudioInput(pcm16=b"\x00\x01" * 48000, sample_rate=48000)
    stt_class(device="cpu", cap_tokens=True).transcribe(one_second_48k)
    assert FakeModel.calls[-1]["max_new_tokens"] == 10 + 2  # 1 s -> max(12, 6 + 4)


def test_bad_context_mode(stt_class):
    with pytest.raises(ValueError):
        stt_class(device="cpu", context_mode="magic")
