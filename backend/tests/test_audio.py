import os
import time

import numpy as np

from app.ai.audio import float_to_pcm16, pcm16_to_float, read_wav, resample, wav_bytes
from app.users.audio_store import AudioStore


def test_pcm_round_trip():
    x = np.array([0.0, 0.5, -0.5, 0.999], dtype=np.float32)
    assert np.allclose(pcm16_to_float(float_to_pcm16(x)), x, atol=1e-4)


def test_resample_length_and_identity():
    x = np.sin(np.linspace(0, 10, 24000)).astype(np.float32)
    assert len(resample(x, 24000, 16000)) == 16000
    assert resample(x, 16000, 16000) is not None
    assert len(resample(np.array([], dtype=np.float32), 24000, 16000)) == 0


def test_wav_round_trip():
    x = np.linspace(-0.5, 0.5, 2400).astype(np.float32)
    samples, rate = read_wav(wav_bytes(x, 24000))
    assert rate == 24000 and len(samples) == 2400


def test_audio_store_saves_and_expires(tmp_path):
    store = AudioStore(tmp_path, retention_days=7)
    path = store.save("s1", 3, b"\x00\x00" * 160, 16000)
    assert path.name == "003.wav" and path.is_file()
    assert store.cleanup() == 0
    old = time.time() - 8 * 86400
    os.utime(path.parent, (old, old))
    assert store.cleanup() == 1
    assert not path.parent.exists()


def test_cleanup_without_folder(tmp_path):
    assert AudioStore(tmp_path / "missing", 7).cleanup() == 0
