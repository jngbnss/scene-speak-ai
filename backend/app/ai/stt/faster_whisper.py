"""faster-whisper STT adapter (https://github.com/SYSTRAN/faster-whisper)."""

import threading
import time

from app.ai.audio import pcm16_to_float, resample
from app.ai.runtime import ensure_pyav_or_placeholder, register_cuda_dll_dirs
from app.ai.types import AdapterError, AudioInput, Transcript, WordInfo

WHISPER_RATE = 16000
# Speech runs at ~3 words/s; generous cap that still stops runaway repetition loops.
TOKENS_PER_SECOND = 6
MIN_TOKENS = 12

# How menu words are given to Whisper (EXP-ASR-001):
#   "hotwords": faster-whisper hotwords (prefix tokens)
#   "prompt":   a natural sentence containing the words, as initial_prompt
#   "none":     no context
CONTEXT_MODES = ("hotwords", "prompt", "none")


class FasterWhisperSTT:
    def __init__(
        self,
        model: str = "small.en",
        *,
        device: str = "cuda",
        compute_type: str = "int8_float16",
        beam_size: int = 1,
        context_mode: str = "prompt",
        cap_tokens: bool = False,  # capping truncated words (EXP-ASR-001, condition G)
    ) -> None:
        if context_mode not in CONTEXT_MODES:
            raise ValueError(f"context_mode must be one of {CONTEXT_MODES}")
        if device == "cuda":
            register_cuda_dll_dirs()
        ensure_pyav_or_placeholder()
        from faster_whisper import WhisperModel

        self.model_id = f"faster-whisper:{model}:{device}:{compute_type}"
        self._model = WhisperModel(model, device=device, compute_type=compute_type)
        self._beam_size = beam_size
        self._context_mode = context_mode
        self._cap_tokens = cap_tokens
        self._lock = threading.Lock()  # one decode at a time; the model is not re-entrant

    def transcribe(self, audio: AudioInput, *, hotwords: list[str] | None = None) -> Transcript:
        samples = resample(pcm16_to_float(audio.pcm16), audio.sample_rate, WHISPER_RATE)
        context: dict = {}
        if hotwords and self._context_mode == "hotwords":
            context["hotwords"] = " ".join(hotwords)
        elif hotwords and self._context_mode == "prompt":
            context["initial_prompt"] = f"A customer orders at a café: {', '.join(hotwords)}."
        if self._cap_tokens:
            seconds = len(samples) / WHISPER_RATE
            context["max_new_tokens"] = max(MIN_TOKENS, int(seconds * TOKENS_PER_SECOND) + 4)
        started = time.perf_counter()
        try:
            with self._lock:
                segments, info = self._model.transcribe(
                    samples,
                    language="en",
                    beam_size=self._beam_size,
                    word_timestamps=True,
                    vad_filter=False,  # the browser already cut the utterance (Silero VAD)
                    condition_on_previous_text=False,
                    **context,
                )
                segments = list(segments)
        except Exception as exc:  # CUDA OOM, corrupt audio, ...
            raise AdapterError(f"Whisper failed: {exc}") from exc
        words = [
            WordInfo(
                word=w.word.strip(),
                start=round(w.start, 3),
                end=round(w.end, 3),
                confidence=round(w.probability, 3),
            )
            for s in segments
            for w in (s.words or [])
            if w.word.strip()
        ]
        return Transcript(
            text=" ".join(s.text.strip() for s in segments).strip(),
            words=words,
            language=info.language,
            audio_duration_ms=audio.duration_ms,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_id=self.model_id,
        )

    def warm_up(self) -> None:
        """The first CUDA decode takes ~25 s; do it before the first user speaks."""
        silence = AudioInput(pcm16=b"\x00\x00" * WHISPER_RATE, sample_rate=WHISPER_RATE)
        self.transcribe(silence)
