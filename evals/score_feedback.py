"""Scores the Learning Evaluator's grammar detection against human labels.

    cd backend
    .venv/Scripts/python ../evals/score_feedback.py --provider ollama --label baseline

A predicted grammar error is a true positive when it quotes the same customer line as a
gold error (the line containing the gold "original"). Error types are reported but not
required to match. Lines the labeler marked error-free that get a correction count as
false feedback, the failure users notice most.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.registry import get_llm  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.evaluation.evaluator import Evaluator, SessionSummary, UserLine  # noqa: E402
from app.scenes.loader import load_scene  # noqa: E402


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()


def line_of(lines: list[str], quote: str) -> int | None:
    q = _words(quote)
    for i, line in enumerate(lines):
        w = _words(line)
        if any(w[j : j + len(q)] == q for j in range(len(w) - len(q) + 1)):
            return i
    return None


def score(provider: str, cases_path: Path) -> dict:
    llm = get_llm(Settings(llm_provider=provider))
    evaluator = Evaluator(load_scene("new-york-cafe"), llm)
    cases = [
        json.loads(x) for x in cases_path.read_text(encoding="utf-8").splitlines() if x.strip()
    ]

    tp = fp = fn = 0
    false_feedback_cases = 0
    details = []
    for case in cases:
        lines = case["lines"]
        transcript = [("npc", "Hi there! What can I get for you today?")]
        for line in lines:
            transcript += [("user", line), ("npc", "Okay.")]
        fb = evaluator.evaluate(
            SessionSummary(
                transcript=transcript,
                user_lines=[UserLine(i + 1, t) for i, t in enumerate(lines)],
                success=True,
                missing_required=[],
            )
        )
        gold_lines = {line_of(lines, g["original"]) for g in case["gold"]}
        pred_lines = {line_of(lines, e.original) for e in fb.grammar_errors} - {None}
        c_tp = len(gold_lines & pred_lines)
        c_fp = len(pred_lines - gold_lines)
        c_fn = len(gold_lines - pred_lines)
        tp, fp, fn = tp + c_tp, fp + c_fp, fn + c_fn
        false_feedback_cases += not case["gold"] and bool(pred_lines)
        details.append(
            {
                "id": case["id"],
                "gold": case["gold"],
                "predicted": [e.model_dump() for e in fb.grammar_errors],
                "unnatural": [e.model_dump() for e in fb.unnatural_expressions],
                "tp": c_tp,
                "fp": c_fp,
                "fn": c_fn,
                "source": fb.source,
            }
        )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    clean = sum(1 for c in cases if not c["gold"])
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "model_id": getattr(llm, "model_id", provider),
        "cases": len(cases),
        "metrics": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "false_feedback_rate": round(fp / (tp + fp), 3) if tp + fp else 0.0,
            "clean_cases_flagged": f"{false_feedback_cases}/{clean}",
            "tp": tp,
            "fp": fp,
            "fn": fn,
        },
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--label", default="run")
    parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "feedback-cases.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "evals" / "results")
    args = parser.parse_args()

    report = {"label": args.label, **score(args.provider, args.cases)}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{datetime.now():%Y%m%d-%H%M}-feedback-{args.label}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2, ensure_ascii=False))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
