"""Small PCM helpers (stdlib + numpy only)."""

import io
import wave

import numpy as np


def pcm16_to_float(pcm16: bytes) -> np.ndarray:
    return np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0


def float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def rms_dbfs(pcm16: bytes) -> float:
    """Loudness of 16-bit PCM in dB relative to full scale (silence = -inf)."""
    samples = pcm16_to_float(pcm16)
    if len(samples) == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    return 20 * np.log10(rms) if rms > 0 else float("-inf")


def resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Linear resampling. Good enough for speech going into Whisper."""
    if src_rate == dst_rate or len(samples) == 0:
        return samples.astype(np.float32)
    n_out = int(round(len(samples) * dst_rate / src_rate))
    positions = np.linspace(0, len(samples) - 1, n_out)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(float_to_pcm16(samples))
    return buffer.getvalue()


def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        if w.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV is supported")
        frames = w.readframes(w.getnframes())
        samples = pcm16_to_float(frames)
        if w.getnchannels() > 1:
            samples = samples.reshape(-1, w.getnchannels()).mean(axis=1)
        return samples.astype(np.float32), w.getframerate()
