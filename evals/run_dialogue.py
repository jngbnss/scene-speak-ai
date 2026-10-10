"""Runs evals/dialogue-cases.jsonl through the NPC and reports dialogue-quality metrics.

    cd backend
    .venv/Scripts/python ../evals/run_dialogue.py --provider ollama --label baseline

Metrics (per NPC reply):
- scene_deviation_rate: first LLM reply rejected by the output guard
- menu_hallucination_rate: first LLM reply mentioned an off-menu item
- retry_rate / template_fallback_rate: how often the guard forced a retry / template
- action_accuracy: Director action matched the expected action (rules + LLM assist)
- latency: LLM time per NPC reply, including a retry when one happened
"""

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.registry import get_llm  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.scenes.conversation import ConversationSession  # noqa: E402
from app.scenes.loader import load_scene  # noqa: E402


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True)
        return out.stdout.decode().strip() or "unknown"
    except OSError:
        return "unknown"


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def run(provider: str, cases_path: Path, limit: int | None) -> dict:
    settings = Settings(llm_provider=provider)
    llm = get_llm(settings)
    cases = [
        json.loads(x) for x in cases_path.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    cases = cases[:limit] if limit else cases

    replies, expected, matched, samples = [], 0, 0, []
    for case in cases:
        session = ConversationSession(load_scene(case["scene"]), llm=llm)
        session.start()
        for step in case["turns"]:
            result = session.handle_text(step["user"])
            want = step.get("expect", {}).get("action")
            if want:
                expected += 1
                matched += result.turn.action == want
            if result.reply.first_violations and len(samples) < 15:
                samples.append(
                    {
                        "case": case["id"],
                        "action": result.turn.action,
                        "violations": result.reply.first_violations,
                        "final": result.reply.text,
                    }
                )
        replies += session.replies

    llm_replies = [r for r in replies if r.source != "template"]
    n = len(llm_replies) or 1
    first_bad = [r for r in llm_replies if r.first_violations]
    off_menu = [r for r in first_bad if any(v.startswith("off-menu") for v in r.first_violations)]
    latencies = [r.llm_latency_ms for r in llm_replies if r.llm_latency_ms]
    return {
        "label": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "provider": provider,
        "model_id": getattr(llm, "model_id", provider),
        "cases": len(cases),
        "npc_replies": len(llm_replies),
        "metrics": {
            "scene_deviation_rate": round(len(first_bad) / n, 3),
            "menu_hallucination_rate": round(len(off_menu) / n, 3),
            "retry_rate": round(sum(r.attempts == 2 for r in llm_replies) / n, 3),
            "template_fallback_rate": round(
                sum(r.source == "template_fallback" for r in llm_replies) / n, 3
            ),
            "final_guard_pass_rate": round(sum(r.guard.ok for r in replies) / len(replies), 3),
            "action_accuracy": round(matched / expected, 3) if expected else None,
            "latency_ms_mean": round(statistics.mean(latencies)) if latencies else 0,
            "latency_ms_p50": percentile(latencies, 0.5),
            "latency_ms_p95": percentile(latencies, 0.95),
        },
        "violation_samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--label", default="run")
    parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "dialogue-cases.jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "results")
    args = parser.parse_args()

    report = run(args.provider, args.cases, args.limit)
    report["label"] = args.label
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{datetime.now():%Y%m%d-%H%M}-dialogue-{args.label}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
