import type { MetricInfo } from "./compare";

/** Same table as METRIC_INFO in evals/run.py, for result files written before it existed. */
export const DEFAULT_INFO: Record<string, MetricInfo> = {
  "dialogue.scene_deviation_rate": { better: "lower", label: "NPC 장면 이탈률" },
  "dialogue.menu_hallucination_rate": { better: "lower", label: "NPC 메뉴 환각률" },
  "dialogue.retry_rate": { better: "lower", label: "NPC 재생성률" },
  "dialogue.template_fallback_rate": { better: "lower", label: "NPC 템플릿 대체율" },
  "dialogue.final_guard_pass_rate": { better: "higher", label: "최종 가드 통과율" },
  "dialogue.action_accuracy": { better: "higher", label: "Director 행동 정확도" },
  "dialogue.latency_ms_mean": { better: "lower", label: "NPC 응답 평균 (ms)" },
  "dialogue.latency_ms_p50": { better: "lower", label: "NPC 응답 p50 (ms)" },
  "dialogue.latency_ms_p95": { better: "lower", label: "NPC 응답 p95 (ms)" },
  "feedback.precision": { better: "higher", label: "피드백 정밀도" },
  "feedback.recall": { better: "higher", label: "피드백 재현율" },
  "feedback.f1": { better: "higher", label: "피드백 F1" },
  "feedback.false_feedback_rate": { better: "lower", label: "잘못된 지적 비율" },
  "asr.n": { label: "음성 파일 수" },
  "asr.wer": { better: "lower", label: "음성인식 WER" },
  "asr.slot_accuracy": { better: "higher", label: "주문 정보 인식률" },
  "asr.latency_ms_p50": { better: "lower", label: "음성인식 p50 (ms)" },
  "asr.latency_ms_p95": { better: "lower", label: "음성인식 p95 (ms)" },
  "asr.rtf_mean": { better: "lower", label: "음성인식 RTF" },
};
