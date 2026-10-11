"""wav2vec2 English forced aligner (ONNX export of facebook/wav2vec2-base-960h).

Runs only after a session ends, never inside the live turn loop. Uses onnxruntime and a
numpy CTC aligner instead of WhisperX/torchaudio so no torch install is needed (D-027).
"""

import json
import threading
import time
from pathlib import Path

import numpy as np

from app.ai.alignment.ctc import align_words, log_softmax
from app.ai.audio import pcm16_to_float, resample
from app.ai.runtime import register_cuda_dll_dirs
from app.ai.types import AdapterError, AlignedWord, AudioInput

REPO_ID = "Xenova/wav2vec2-base-960h"  # ONNX export of facebook/wav2vec2-base-960h (Apache-2.0)
REVISION = "a19f851b3d42865797e410752b4c570c871e4825"
SAMPLE_RATE = 16000


def download_model(repo_id: str = REPO_ID, revision: str = REVISION) -> Path:
    """Fetches the model into the Hugging Face cache (~380 MB) and returns its folder."""
    from huggingface_hub import hf_hub_download

    for name in ("vocab.json", "onnx/model.onnx"):
        path = hf_hub_download(repo_id, name, revision=revision)
    return Path(path).parents[1]


class Wav2Vec2Aligner:
    def __init__(self, model_dir: Path | None = None, *, device: str = "cpu") -> None:
        try:
            model_dir = model_dir or download_model()
        except Exception as exc:
            raise AdapterError(f"wav2vec2 model unavailable: {exc}") from exc
        model_path = model_dir / "onnx" / "model.onnx"
        vocab_path = model_dir / "vocab.json"
        if not model_path.is_file() or not vocab_path.is_file():
            raise AdapterError(f"wav2vec2 model files not found in {model_dir}")
        if device == "cuda":
            register_cuda_dll_dirs()
        import onnxruntime as ort

        providers = ["CPUExecutionProvider"]
        if device == "cuda" and "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        self._session = ort.InferenceSession(str(model_path), providers=providers)
        self.device = "cuda" if "CUDAExecutionProvider" in self._session.get_providers() else "cpu"
        self.model_id = f"wav2vec2-base-960h-onnx:{self.device}"
        self._vocab: dict[str, int] = json.loads(vocab_path.read_text(encoding="utf-8"))
        self._lock = threading.Lock()
        self.last_latency_ms = 0

    def emissions(self, samples: np.ndarray) -> np.ndarray:
        """Per-frame log probabilities, shape (frames, vocab). One frame is ~20 ms."""
        x = (samples - samples.mean()) / np.sqrt(samples.var() + 1e-7)
        with self._lock:
            (logits,) = self._session.run(None, {"input_values": x[None, :].astype(np.float32)})
        return log_softmax(logits[0].astype(np.float32))

    def align(self, audio: AudioInput, text: str) -> list[AlignedWord]:
        started = time.perf_counter()
        samples = resample(pcm16_to_float(audio.pcm16), audio.sample_rate, SAMPLE_RATE)
        if len(samples) < SAMPLE_RATE // 10 or not text.split():
            return []
        try:
            log_probs = self.emissions(samples)
        except Exception as exc:
            raise AdapterError(f"wav2vec2 failed: {exc}") from exc
        seconds_per_frame = len(samples) / SAMPLE_RATE / log_probs.shape[0]
        spans = align_words(log_probs, text.split(), self._vocab)
        words: list[AlignedWord] = []
        for span in spans:
            start = round(span.start_frame * seconds_per_frame, 3)
            end = round(span.end_frame * seconds_per_frame, 3)
            pause = int(round((start - words[-1].end) * 1000)) if words else 0
            words.append(
                AlignedWord(
                    word=span.word,
                    start=start,
                    end=end,
                    confidence=span.score,
                    pause_before_ms=max(pause, 0),
                )
            )
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)
        return words
