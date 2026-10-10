from app.ai.types import AlignedWord, AudioInput


class MockAligner:
    """Spreads words evenly across the audio. No pauses."""

    model_id = "mock-aligner"

    def align(self, audio: AudioInput, text: str) -> list[AlignedWord]:
        tokens = text.split()
        if not tokens:
            return []
        step = audio.duration_ms / 1000 / len(tokens)
        return [
            AlignedWord(
                word=w,
                start=round(i * step, 3),
                end=round((i + 1) * step, 3),
                confidence=None,
                pause_before_ms=0,
            )
            for i, w in enumerate(tokens)
        ]
