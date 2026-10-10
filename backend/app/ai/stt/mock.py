import time

from app.ai.types import AudioInput, Transcript, WordInfo


class MockSTT:
    """Returns a fixed transcript. ``transcripts`` maps ``AudioInput.source_name`` to text."""

    model_id = "mock-stt"

    def __init__(self, transcripts: dict[str, str] | None = None, default_text: str = "") -> None:
        self._transcripts = transcripts or {}
        self._default_text = default_text

    def transcribe(self, audio: AudioInput, *, hotwords: list[str] | None = None) -> Transcript:
        started = time.perf_counter()
        text = self._transcripts.get(audio.source_name or "", self._default_text)
        tokens = text.split()
        duration_s = audio.duration_ms / 1000
        step = duration_s / len(tokens) if tokens else 0.0
        words = [
            WordInfo(word=w, start=round(i * step, 3), end=round((i + 1) * step, 3), confidence=1.0)
            for i, w in enumerate(tokens)
        ]
        return Transcript(
            text=text,
            words=words,
            language="en",
            audio_duration_ms=audio.duration_ms,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_id=self.model_id,
        )
