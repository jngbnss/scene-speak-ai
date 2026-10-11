/** Mirrors evals/compare.py so the /report page and the CLI agree. */
import { DEFAULT_INFO } from "./metricInfo";

export interface MetricInfo {
  better?: "lower" | "higher";
  label?: string;
}

export interface CompareRow {
  metric: string;
  label: string;
  old: number | null;
  new: number | null;
  delta: number | null;
  changePct: number | null;
  verdict: "개선" | "악화" | "=" | "—";
}

const KINDS = ["dialogue", "feedback", "asr"] as const;

export function kindOf(data: Record<string, unknown>, name: string): string {
  if (typeof data.kind === "string") return data.kind;
  return KINDS.find((k) => name.includes(`-${k}-`)) ?? "unknown";
}

function numbers(source: unknown, prefix: string): Record<string, number> {
  const out: Record<string, number> = {};
  if (source && typeof source === "object") {
    for (const [k, v] of Object.entries(source)) {
      if (typeof v === "number") out[prefix ? `${prefix}.${k}` : k] = v;
    }
  }
  return out;
}

/** Flat numeric metrics ("asr.wer": 0.03) from a suite file or an older single file. */
export function flatten(data: Record<string, unknown>, name: string): Record<string, number> {
  const kind = kindOf(data, name);
  if (kind === "suite") return numbers(data.metrics, "");
  return numbers(kind === "asr" ? data.overall : data.metrics, kind);
}

export function metricInfo(...files: Record<string, unknown>[]): Record<string, MetricInfo> {
  return Object.assign(
    { ...DEFAULT_INFO },
    ...files.map((f) => (f.metric_info ?? {}) as Record<string, MetricInfo>),
  );
}

export function compareMetrics(
  oldM: Record<string, number>,
  newM: Record<string, number>,
  info: Record<string, MetricInfo>,
): CompareRow[] {
  const names = [...new Set([...Object.keys(oldM), ...Object.keys(newM)])].sort();
  return names.map((metric) => {
    const a = metric in oldM ? oldM[metric] : null;
    const b = metric in newM ? newM[metric] : null;
    const better = info[metric]?.better;
    let verdict: CompareRow["verdict"] = "—";
    if (a !== null && b !== null) {
      if (a === b || !better) verdict = "=";
      else verdict = (better === "lower" ? b < a : b > a) ? "개선" : "악화";
    }
    return {
      metric,
      label: info[metric]?.label ?? metric,
      old: a,
      new: b,
      delta: a !== null && b !== null ? b - a : null,
      changePct: a !== null && b !== null && a !== 0 ? ((b - a) / a) * 100 : null,
      verdict,
    };
  });
}

export function formatValue(v: number | null): string {
  if (v === null) return "—";
  if (Number.isInteger(v) || Math.abs(v) >= 100) return String(Math.round(v));
  return v.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}
