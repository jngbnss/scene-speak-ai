import { describe, expect, it } from "vitest";

import { compareMetrics, flatten, formatValue, metricInfo } from "../src/features/report/compare";

describe("report comparison (mirrors evals/compare.py)", () => {
  it("flattens suite files and older single-kind files", () => {
    expect(flatten({ kind: "suite", metrics: { "asr.wer": 0.03 } }, "x.json")).toEqual({ "asr.wer": 0.03 });
    expect(flatten({ overall: { wer: 0.05, n: 240 } }, "20261011-0705-asr-A.json")).toEqual({
      "asr.wer": 0.05,
      "asr.n": 240,
    });
    expect(
      flatten({ metrics: { f1: 0.9, clean_cases_flagged: "1/3" } }, "20261011-0621-feedback-b.json"),
    ).toEqual({ "feedback.f1": 0.9 });
  });

  it("judges changes by the metric's direction", () => {
    const info = metricInfo({
      metric_info: { "asr.wer": { better: "lower", label: "WER" }, "feedback.f1": { better: "higher" } },
    });
    const rows = compareMetrics(
      { "asr.wer": 0.05, "feedback.f1": 0.9, "asr.n": 240, "dialogue.x": 1 },
      { "asr.wer": 0.03, "feedback.f1": 0.8, "asr.n": 240 },
      info,
    );
    const by = Object.fromEntries(rows.map((r) => [r.metric, r]));
    expect(by["asr.wer"].verdict).toBe("개선");
    expect(by["asr.wer"].label).toBe("WER");
    expect(by["asr.wer"].changePct).toBeCloseTo(-40);
    expect(by["feedback.f1"].verdict).toBe("악화");
    expect(by["asr.n"].verdict).toBe("=");
    expect(by["dialogue.x"]).toMatchObject({ new: null, delta: null, verdict: "—" });
  });

  it("formats values compactly", () => {
    expect(formatValue(0.0500)).toBe("0.05");
    expect(formatValue(1233)).toBe("1233");
    expect(formatValue(null)).toBe("—");
  });
});
