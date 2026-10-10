"""Real speech models. Excluded by default; run with:  pytest -m model"""

import pytest

from app.ai.audio import float_to_pcm16, read_wav, resample
from app.ai.types import AudioInput
from app.core.config import Settings

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(_env_file=None)


def test_kokoro_then_whisper_round_trip(settings):
    from app.ai.stt.faster_whisper import FasterWhisperSTT
    from app.ai.tts.kokoro import KokoroTTS

    tts = KokoroTTS(settings.kokoro_model_path, settings.kokoro_voices_path)
    speech = tts.synthesize("Can I get a large hot latte with oat milk?", voice="am_michael")
    samples, rate = read_wav(speech.wav_bytes)
    pcm = float_to_pcm16(resample(samples, rate, 16000))

    stt = FasterWhisperSTT(settings.whisper_model, device=settings.whisper_device)
    result = stt.transcribe(AudioInput(pcm16=pcm, sample_rate=16000), hotwords=["oat milk"])
    assert "latte" in result.text.lower() and "oat" in result.text.lower()
    assert all(w.confidence is not None for w in result.words)
