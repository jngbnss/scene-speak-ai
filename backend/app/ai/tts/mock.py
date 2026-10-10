import io
import time
import wave

from app.ai.types import SpeechAudio

SAMPLE_RATE = 24000


def silent_wav(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * int(sample_rate * duration_ms / 1000))
    return buffer.getvalue()


class MockTTS:
    """Returns silence whose length roughly follows the text length."""

    model_id = "mock-tts"

    def synthesize(self, text: str, *, voice: str) -> SpeechAudio:
        started = time.perf_counter()
        duration_ms = min(len(text) * 50, 10_000)
        return SpeechAudio(
            wav_bytes=silent_wav(duration_ms),
            sample_rate=SAMPLE_RATE,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_id=self.model_id,
        )
