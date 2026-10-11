"""EXP-ASR-001: compares Whisper settings on a manifest of recordings.

    cd backend
    .venv/Scripts/python ../evals/asr/run_asr.py --model small.en --label small-prompt
    .venv/Scripts/python ../evals/asr/run_asr.py --context-mode none --label small-plain

Manifest (JSONL): {"file": "x.wav", "text": "reference", "condition": "clean", ...}
Metrics, overall and per condition:
- WER after normalization (lowercase, punctuation removed, simple number words)
- slot accuracy: the Director's rule extractor reads the hypothesis and the reference;
  correct when every slot and the unavailable item match (= intent recognition)
- latency p50/p95 and real-time factor (processing time / audio length)
"""

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.audio import float_to_pcm16, read_wav, resample  # noqa: E402
from app.ai.stt.faster_whisper import FasterWhisperSTT  # noqa: E402
from app.ai.types import AudioInput  # noqa: E402
from app.scenes.extractor import RuleExtractor  # noqa: E402
from app.scenes.loader import load_scene  # noqa: E402

NUMBERS = {"1": "one", "2": "two", "3": "three"}


def normalize(text: str) -> list[str]:
    words = re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("’", "'")).split()
    return [NUMBERS.get(w, w) for w in words]


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))] if s else 0.0


def summarize(rows: list[dict]) -> dict:
    words = sum(r["ref_words"] for r in rows)
    lat = [r["latency_ms"] for r in rows]
    return {
        "n": len(rows),
        "wer": round(sum(r["errors"] for r in rows) / max(words, 1), 4),
        "slot_accuracy": round(sum(r["slots_ok"] for r in rows) / max(len(rows), 1), 4),
        "latency_ms_p50": round(pct(lat, 0.5)),
        "latency_ms_p95": round(pct(lat, 0.95)),
        "rtf_mean": round(statistics.mean(r["rtf"] for r in rows), 3) if rows else 0,
    }


def evaluate(
    manifest: Path,
    *,
    model: str = "small.en",
    device: str = "cuda",
    compute_type: str = "int8_float16",
    context_mode: str = "prompt",
    token_cap: bool = True,
) -> dict:
    """Transcribes every manifest entry. context_mode "none" sends no scene vocabulary."""
    scene = load_scene("new-york-cafe")
    extractor = RuleExtractor(scene)
    hotwords = None if context_mode == "none" else scene.hotwords
    stt = FasterWhisperSTT(
        model,
        device=device,
        compute_type=compute_type,
        context_mode=context_mode,
        cap_tokens=token_cap,
    )
    entries = [
        json.loads(x) for x in manifest.read_text(encoding="utf-8").splitlines() if x.strip()
    ]

    # The first CUDA decode is slow; keep it out of the latency numbers.
    stt.transcribe(AudioInput(pcm16=b"\x00\x00" * 16000))

    rows = []
    for i, e in enumerate(entries, 1):
        samples, rate = read_wav((manifest.parent / e["file"]).read_bytes())
        pcm = float_to_pcm16(resample(samples, rate, 16000))
        audio = AudioInput(pcm16=pcm, sample_rate=16000)
        started = time.perf_counter()
        hyp = stt.transcribe(audio, hotwords=hotwords)
        elapsed_ms = (time.perf_counter() - started) * 1000
        ref_w, hyp_w = normalize(e["text"]), normalize(hyp.text)
        ref_x, hyp_x = extractor.extract(e["text"]), extractor.extract(hyp.text)
        rows.append(
            {
                **e,
                "hypothesis": hyp.text,
                "ref_words": len(ref_w),
                "errors": edit_distance(ref_w, hyp_w),
                "slots_ok": ref_x.slots == hyp_x.slots and ref_x.unknown_item == hyp_x.unknown_item,
                "latency_ms": round(elapsed_ms),
                "rtf": round(elapsed_ms / max(audio.duration_ms, 1), 3),
            }
        )
        print(f"{i}/{len(entries)}", end="\r")

    conditions = sorted({r["condition"] for r in rows})
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model_id": stt.model_id,
        "hotwords": hotwords,
        "context_mode": context_mode,
        "token_cap": token_cap,
        "manifest": str(manifest.relative_to(ROOT) if manifest.is_relative_to(ROOT) else manifest),
        "synthetic": all(r.get("synthetic") for r in rows),
        "overall": summarize(rows),
        "by_condition": {
            c: summarize([r for r in rows if r["condition"] == c]) for c in conditions
        },
        "errors": [
            {k: r[k] for k in ("file", "text", "hypothesis", "slots_ok")}
            for r in rows
            if r["errors"] or not r["slots_ok"]
        ][:40],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "evals/audio/synthetic/manifest.jsonl"
    )
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="int8_float16")
    parser.add_argument("--context-mode", default="prompt", choices=["hotwords", "prompt", "none"])
    parser.add_argument("--no-token-cap", action="store_true")
    parser.add_argument("--label", default="run")
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "results")
    args = parser.parse_args()

    report = {
        "label": args.label,
        **evaluate(
            args.manifest,
            model=args.model,
            device=args.device,
            compute_type=args.compute_type,
            context_mode=args.context_mode,
            token_cap=not args.no_token_cap,
        ),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{datetime.now():%Y%m%d-%H%M}-asr-{args.label}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps({"overall": report["overall"], "by_condition": report["by_condition"]}, indent=2)
    )
    print(f"saved {path}")


if __name__ == "__main__":
    main()
