import { describe, expect, it } from "vitest";

import { segmentReason, shadowSummary } from "../src/features/speech/format";
import type { ShadowResult } from "../src/types/messages";

const base: ShadowResult = {
  reference: "Can I get a latte?",
  heard: "Can I get a latte",
  words: [],
  missing: [],
  extra: [],
  matched_ratio: 1,
  speech: null,
};

describe("speech hint wording", () => {
  it("explains why a segment is worth replaying", () => {
    expect(segmentReason({ start: 0, end: 1, reasons: ["pause"], text: "a" })).toBe("말이 길게 멈춘 곳");
    expect(segmentReason({ start: 0, end: 1, reasons: ["pause", "uncertain"], text: "a" })).toBe(
      "말이 길게 멈춘 곳 · 인식이 불확실한 단어",
    );
  });

  it("summarizes read-aloud results without scores", () => {
    expect(shadowSummary(base)).toBe("빠진 단어 없이 모두 말했어요.");
    expect(shadowSummary({ ...base, missing: ["a"], extra: ["the", "uh"] })).toBe(
      "빠진 단어 1개, 덧붙인 단어 2개",
    );
    expect(shadowSummary({ ...base, heard: " " })).toContain("알아듣지 못했어요");
    expect(shadowSummary({ ...base, words: [{ word: "latte", status: "unclear" }] })).toContain("불확실");
  });
});
