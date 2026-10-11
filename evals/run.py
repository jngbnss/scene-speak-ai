"""Evaluation harness: runs the dialogue, feedback and ASR evaluations into one result file.

    cd backend
    .venv/Scripts/python ../evals/run.py --label baseline
    .venv/Scripts/python ../evals/run.py --label asr-plain --asr-context none --only asr
    .venv/Scripts/python ../evals/compare.py <old>.json <new>.json

The result goes to evals/results/{YYYYMMDD-HHMM}-suite-{label}.json with the models,
settings, git commit and flat metrics ("dialogue.scene_deviation_rate", "asr.wer", ...),
so two runs on the same data can be compared by evals/compare.py or the /report page.
Results are committed (D-018): they are small and they are the experiment record.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "evals"))

SECTIONS = ("dialogue", "feedback", "asr")

# Direction tells compare.py and the report page whether a rise is an improvement.
METRIC_INFO: dict[str, dict] = {
    "dialogue.scene_deviation_rate": {"better": "lower", "label": "NPC 장면 이탈률"},
    "dialogue.menu_hallucination_rate": {"better": "lower", "label": "NPC 메뉴 환각률"},
    "dialogue.retry_rate": {"better": "lower", "label": "NPC 재생성률"},
    "dialogue.template_fallback_rate": {"better": "lower", "label": "NPC 템플릿 대체율"},
    "dialogue.final_guard_pass_rate": {"better": "higher", "label": "최종 가드 통과율"},
    "dialogue.action_accuracy": {"better": "higher", "label": "Director 행동 정확도"},
    "dialogue.latency_ms_mean": {"better": "lower", "label": "NPC 응답 평균 (ms)"},
    "dialogue.latency_ms_p50": {"better": "lower", "label": "NPC 응답 p50 (ms)"},
    "dialogue.latency_ms_p95": {"better": "lower", "label": "NPC 응답 p95 (ms)"},
    "feedback.precision": {"better": "higher", "label": "피드백 정밀도"},
    "feedback.recall": {"better": "higher", "label": "피드백 재현율"},
    "feedback.f1": {"better": "higher", "label": "피드백 F1"},
    "feedback.false_feedback_rate": {"better": "lower", "label": "잘못된 지적 비율"},
    "asr.n": {"label": "음성 파일 수"},
    "asr.wer": {"better": "lower", "label": "음성인식 WER"},
    "asr.slot_accuracy": {"better": "higher", "label": "주문 정보 인식률"},
    "asr.latency_ms_p50": {"better": "lower", "label": "음성인식 p50 (ms)"},
    "asr.latency_ms_p95": {"better": "lower", "label": "음성인식 p95 (ms)"},
    "asr.rtf_mean": {"better": "lower", "label": "음성인식 RTF"},
}


def git_info() -> dict:
    def run(*args: str) -> str:
        try:
            out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
            return out.stdout.decode().strip()
        except OSError:
            return ""

    return {
        "commit": run("rev-parse", "--short", "HEAD") or "unknown",
        "dirty": bool(run("status", "--porcelain")),
    }


def numeric(metrics: dict, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}.{k}": v
        for k, v in metrics.items()
        if isinstance(v, int | float) and not isinstance(v, bool)
    }


def run_dialogue_section(provider: str) -> dict:
    import run_dialogue

    report = run_dialogue.run(provider, ROOT / "evals" / "dialogue-cases.jsonl", None, None)
    return {
        "model_id": report["model_id"],
        "cases": report["cases"],
        "npc_replies": report["npc_replies"],
        "metrics": report["metrics"],
        "violation_samples": report["violation_samples"],
    }


def run_feedback_section(provider: str) -> dict:
    import score_feedback

    report = score_feedback.score(provider, ROOT / "evals" / "feedback-cases.jsonl")
    return {k: report[k] for k in ("model_id", "cases", "metrics", "details")}


def run_asr_section(manifest: Path, model: str, context_mode: str) -> dict:
    from asr import run_asr

    report = run_asr.evaluate(manifest, model=model, context_mode=context_mode)
    return {
        "model_id": report["model_id"],
        "context_mode": report["context_mode"],
        "manifest": report["manifest"],
        "synthetic": report["synthetic"],
        "metrics": report["overall"],
        "by_condition": report["by_condition"],
        "errors": report["errors"],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Korean labels on a Windows console
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--only", nargs="+", choices=SECTIONS, default=list(SECTIONS))
    parser.add_argument("--provider", default="ollama", help="LLM provider for NPC and feedback")
    parser.add_argument("--asr-model", default="small.en")
    parser.add_argument("--asr-context", default="prompt", choices=["prompt", "hotwords", "none"])
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "evals/audio/synthetic/manifest.jsonl"
    )
    parser.add_argument("--note", default="", help="what changed in this run")
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "results")
    args = parser.parse_args()

    if "asr" in args.only and not args.manifest.is_file():
        sys.exit(
            f"ASR manifest not found: {args.manifest}\n"
            "Make the synthetic set first: ../evals/asr/make_synthetic.py (see evals/README.md)"
        )

    started = datetime.now()
    sections: dict[str, dict] = {}
    durations: dict[str, float] = {}
    runners = {
        "dialogue": lambda: run_dialogue_section(args.provider),
        "feedback": lambda: run_feedback_section(args.provider),
        "asr": lambda: run_asr_section(args.manifest, args.asr_model, args.asr_context),
    }
    for name in SECTIONS:
        if name not in args.only:
            continue
        print(f"[{name}] running…", flush=True)
        t = time.perf_counter()
        sections[name] = runners[name]()
        durations[name] = round(time.perf_counter() - t, 1)
        print(f"[{name}] done in {durations[name]} s", flush=True)

    metrics: dict[str, float] = {}
    for name, section in sections.items():
        metrics |= numeric(section["metrics"], name)
    report = {
        "kind": "suite",
        "label": args.label,
        "note": args.note,
        "created_at": started.isoformat(timespec="seconds"),
        "git_commit": (git := git_info())["commit"],
        "git_dirty": git["dirty"],
        "config": {
            "llm_provider": args.provider,
            "asr_model": args.asr_model,
            "asr_context": args.asr_context,
            "sections": list(sections),
        },
        "models": {name: s.get("model_id") for name, s in sections.items()},
        "durations_s": durations,
        "metrics": metrics,
        "metric_info": {k: v for k, v in METRIC_INFO.items() if k in metrics},
        "sections": sections,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{started:%Y%m%d-%H%M}-suite-{args.label}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
