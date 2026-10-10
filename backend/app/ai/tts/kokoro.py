"""Kokoro-82M TTS adapter via kokoro-onnx (https://github.com/thewh1teagle/kokoro-onnx)."""

import threading
import time
from pathlib import Path

from app.ai.audio import wav_bytes
from app.ai.runtime import register_cuda_dll_dirs
from app.ai.types import AdapterError, SpeechAudio


class KokoroTTS:
    def __init__(
        self, model_path: Path, voices_path: Path, *, device: str = "cuda", speed: float = 1.0
    ) -> None:
        if not model_path.is_file() or not voices_path.is_file():
            raise AdapterError(
                f"Kokoro model files not found ({model_path}, {voices_path}). "
                "See README: download kokoro-v1.0.onnx and voices-v1.0.bin into models/kokoro/."
            )
        if device == "cuda":
            register_cuda_dll_dirs()
        import onnxruntime as ort
        from kokoro_onnx import Kokoro

        ort.set_default_logger_severity(3)
        providers = ["CPUExecutionProvider"]
        if device == "cuda" and "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        session = ort.InferenceSession(str(model_path), providers=providers)
        self.device = "cuda" if "CUDAExecutionProvider" in session.get_providers() else "cpu"
        self.model_id = f"kokoro-82m-onnx:{self.device}"
        self._kokoro = Kokoro.from_session(session, str(voices_path))
        self._speed = speed
        self._lock = threading.Lock()

    def synthesize(self, text: str, *, voice: str) -> SpeechAudio:
        started = time.perf_counter()
        try:
            with self._lock:
                samples, sample_rate = self._kokoro.create(
                    text, voice=voice, speed=self._speed, lang="en-us"
                )
        except Exception as exc:
            raise AdapterError(f"Kokoro failed: {exc}") from exc
        return SpeechAudio(
            wav_bytes=wav_bytes(samples, sample_rate),
            sample_rate=sample_rate,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_id=self.model_id,
        )

    def warm_up(self) -> None:
        self.synthesize("Hi.", voice="af_heart")
