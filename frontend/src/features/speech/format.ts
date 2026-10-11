import type { ListenSegment, ShadowResult } from "../../types/messages";

export const seconds = (s: number) => `${s.toFixed(1)}초`;

/** Why a segment is worth replaying, in words a learner understands (no scores). */
export function segmentReason(segment: ListenSegment): string {
  const parts = [];
  if (segment.reasons.includes("pause")) parts.push("말이 길게 멈춘 곳");
  if (segment.reasons.includes("uncertain")) parts.push("인식이 불확실한 단어");
  return parts.join(" · ");
}

export function shadowSummary(result: ShadowResult): string {
  if (!result.heard.trim()) return "말소리를 알아듣지 못했어요. 다시 해 볼까요?";
  if (result.missing.length === 0 && result.extra.length === 0) {
    return result.words.some((w) => w.status === "unclear")
      ? "문장을 모두 말했어요. 물결 표시된 단어는 인식이 불확실했어요."
      : "빠진 단어 없이 모두 말했어요.";
  }
  const parts = [];
  if (result.missing.length) parts.push(`빠진 단어 ${result.missing.length}개`);
  if (result.extra.length) parts.push(`덧붙인 단어 ${result.extra.length}개`);
  return parts.join(", ");
}
