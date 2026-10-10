"""Builds a synthetic ASR test set with Kokoro voices (EXP-ASR-001 stand-in).

    cd backend
    .venv/Scripts/python ../evals/asr/make_synthetic.py

This is NOT Korean-accented speech. It checks the pipeline, the metrics and the effect of
hotwords until real recordings exist (see evals/README.md). Audio goes to
evals/audio/synthetic/ (git-ignored); the manifest lists reference text per file.

"Cafe noise" is synthetic babble: three other script sentences in other voices, mixed at
the given SNR. It avoids third-party noise recordings and their licenses.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.audio import read_wav, resample, wav_bytes  # noqa: E402
from app.ai.tts.kokoro import KokoroTTS  # noqa: E402
from app.core.config import Settings  # noqa: E402

VOICES = ["af_heart", "am_michael", "bf_emma", "bm_george"]
RATE = 16000


def read_script(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [x.strip() for x in lines if x.strip() and not x.startswith("#")]


def mix(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    noise = np.resize(noise, len(speech))
    p_s = np.mean(speech**2) + 1e-12
    p_n = np.mean(noise**2) + 1e-12
    scaled = noise * np.sqrt(p_s / (p_n * 10 ** (snr_db / 10)))
    out = speech + scaled
    return (out / max(1.0, float(np.max(np.abs(out))))).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, default=ROOT / "evals" / "asr" / "script.txt")
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "audio" / "synthetic")
    parser.add_argument("--snr", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    s = Settings(_env_file=None)
    tts = KokoroTTS(s.kokoro_model_path, s.kokoro_voices_path, device=s.kokoro_device)
    sentences = read_script(args.script)
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    clean: dict[tuple[int, str], np.ndarray] = {}
    for i, text in enumerate(sentences):
        for voice in VOICES:
            samples, rate = read_wav(tts.synthesize(text, voice=voice).wav_bytes)
            clean[(i, voice)] = resample(samples, rate, RATE)
        print(f"synthesized {i + 1}/{len(sentences)}", end="\r")

    manifest = []
    for (i, voice), speech in clean.items():
        for condition in ("clean", f"babble{int(args.snr)}db"):
            if condition == "clean":
                samples = speech
            else:
                others = rng.sample([k for k in clean if k[0] != i and k[1] != voice], 3)
                babble = sum(np.resize(clean[k], len(speech)) for k in others)
                samples = mix(speech, babble, args.snr)
            name = f"{i:02d}-{voice}-{condition}.wav"
            (args.out / name).write_bytes(wav_bytes(samples, RATE))
            manifest.append(
                {
                    "file": name,
                    "text": sentences[i],
                    "speaker": voice,
                    "condition": condition,
                    "synthetic": True,
                }
            )
    path = args.out / "manifest.jsonl"
    path.write_text("\n".join(json.dumps(m) for m in manifest) + "\n", encoding="utf-8")
    print(f"\n{len(manifest)} files -> {args.out}")


if __name__ == "__main__":
    main()
