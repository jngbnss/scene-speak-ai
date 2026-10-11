"""Compares two evaluation result files metric by metric.

    cd backend
    .venv/Scripts/python ../evals/compare.py ../evals/results/A.json ../evals/results/B.json
    .venv/Scripts/python ../evals/compare.py A.json B.json --markdown   # for docs/experiments.md

Works with suite files from run.py and with the older single files
(*-dialogue-*, *-feedback-*, *-asr-*). Metrics missing from either file are listed with "—".
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run import METRIC_INFO  # noqa: E402


def kind_of(data: dict, name: str) -> str:
    if data.get("kind"):
        return data["kind"]
    for kind in ("dialogue", "feedback", "asr"):
        if f"-{kind}-" in name:
            return kind
    return "unknown"


def flatten(data: dict, name: str = "") -> dict[str, float]:
    """Flat numeric metrics ("asr.wer": 0.03) from any result file."""
    kind = kind_of(data, name)
    if kind == "suite":
        return dict(data["metrics"])
    source = data.get("overall") if kind == "asr" else data.get("metrics")
    return {
        f"{kind}.{k}": v
        for k, v in (source or {}).items()
        if isinstance(v, int | float) and not isinstance(v, bool)
    }


def load(path: Path) -> tuple[dict, dict[str, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, flatten(data, path.name)


def verdict(metric: str, old: float, new: float, info: dict) -> str:
    better = info.get(metric, {}).get("better")
    if old == new or better is None:
        return "="
    improved = (new < old) if better == "lower" else (new > old)
    return "개선" if improved else "악화"


def compare(old: dict[str, float], new: dict[str, float], info: dict | None = None) -> list[dict]:
    info = {**METRIC_INFO, **(info or {})}
    rows = []
    for metric in sorted(set(old) | set(new), key=lambda m: (m.split(".")[0], m)):
        a, b = old.get(metric), new.get(metric)
        row = {
            "metric": metric,
            "label": info.get(metric, {}).get("label", metric),
            "old": a,
            "new": b,
        }
        if a is not None and b is not None:
            row["delta"] = round(b - a, 4)
            row["change_pct"] = round((b - a) / a * 100, 1) if a else None
            row["verdict"] = verdict(metric, a, b, info)
        rows.append(row)
    return rows


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:g}" if isinstance(v, int) or abs(v) >= 1 else f"{v:.3f}".rstrip("0").rstrip(".")


def render(rows: list[dict], old_name: str, new_name: str, markdown: bool) -> str:
    header = ["지표", old_name, new_name, "변화", "판단"]
    lines = []
    for r in rows:
        delta = "—" if "delta" not in r else f"{r['delta']:+g}"
        if r.get("change_pct") is not None:
            delta += f" ({r['change_pct']:+.1f}%)"
        lines.append([r["label"], _fmt(r["old"]), _fmt(r["new"]), delta, r.get("verdict", "—")])
    if markdown:
        out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        out += ["| " + " | ".join(cells) + " |" for cells in lines]
        return "\n".join(out)
    widths = [max(len(str(c)) for c in col) for col in zip(header, *lines, strict=False)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    return "\n".join(
        [fmt.format(*header), fmt.format(*("-" * w for w in widths))]
        + [fmt.format(*c) for c in lines]
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Korean labels on a Windows console
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    old_data, old = load(args.old)
    new_data, new = load(args.new)
    info = {**old_data.get("metric_info", {}), **new_data.get("metric_info", {})}
    rows = compare(old, new, info)
    if not rows:
        sys.exit("No numeric metrics in common.")
    print(
        render(
            rows,
            old_data.get("label") or args.old.stem,
            new_data.get("label") or args.new.stem,
            args.markdown,
        )
    )
    for data, path in ((old_data, args.old), (new_data, args.new)):
        print(
            f"\n{path.name}: commit {data.get('git_commit', '?')}, {data.get('created_at', '?')}",
            end="",
        )
        if data.get("git_dirty"):
            print(" (uncommitted changes)", end="")
    print()


if __name__ == "__main__":
    main()
