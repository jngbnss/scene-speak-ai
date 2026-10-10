import io
import wave

import pytest

from app.ai import registry
from app.ai.alignment.mock import MockAligner
from app.ai.llm.mock import MockLLM, default_from_schema
from app.ai.stt.mock import MockSTT
from app.ai.tts.mock import MockTTS
from app.ai.types import AudioInput, ChatMessage
from app.core.config import Settings

ONE_SECOND = AudioInput(pcm16=b"\x00\x00" * 16000, source_name="order-1")


def test_mock_stt_returns_mapped_transcript():
    stt = MockSTT({"order-1": "can I get a latte"})
    result = stt.transcribe(ONE_SECOND)
    assert result.text == "can I get a latte"
    assert result.audio_duration_ms == 1000
    assert [w.word for w in result.words] == ["can", "I", "get", "a", "latte"]
    assert result.words[-1].end == pytest.approx(1.0)
    assert result.model_id == "mock-stt"


def test_mock_llm_replays_then_uses_schema_defaults():
    schema = {
        "type": "object",
        "properties": {"reply": {"type": "string"}, "drink": {"type": ["string", "null"]}},
    }
    llm = MockLLM([{"reply": "Sure!", "drink": "latte"}])
    msgs = [ChatMessage(role="user", content="latte")]
    assert llm.generate(msgs, json_schema=schema).parsed == {"reply": "Sure!", "drink": "latte"}
    assert llm.generate(msgs, json_schema=schema).parsed == {"reply": "", "drink": None}
    assert llm.generate(msgs).text == ""
    assert len(llm.calls) == 3


def test_default_from_schema_nested():
    schema = {"type": "object", "properties": {"a": {"type": "array"}, "b": {"type": "integer"}}}
    assert default_from_schema(schema) == {"a": [], "b": 0}


def test_mock_tts_returns_valid_wav():
    audio = MockTTS().synthesize("Hello there", voice="af_heart")
    with wave.open(io.BytesIO(audio.wav_bytes)) as wav:
        assert wav.getframerate() == 24000
        assert wav.getnframes() > 0


def test_mock_aligner_spreads_words():
    words = MockAligner().align(ONE_SECOND, "one two")
    assert [(w.start, w.end) for w in words] == [(0.0, 0.5), (0.5, 1.0)]


def test_registry_defaults_to_mocks():
    s = Settings(_env_file=None)
    assert isinstance(registry.get_stt(s), MockSTT)
    assert isinstance(registry.get_llm(s), MockLLM)
    assert isinstance(registry.get_tts(s), MockTTS)
    assert isinstance(registry.get_aligner(s), MockAligner)


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Available: mock"):
        registry.get_llm(Settings(_env_file=None, llm_provider="gpt"))
