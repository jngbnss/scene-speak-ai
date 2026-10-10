// Mirrors backend/app/api/messages.py. Keep both in sync.

export type SlotValue = string | number | null;

export type ClientMessage =
  | { type: "session_start"; scene_id?: string; nickname?: string }
  | { type: "text_utterance"; seq: number; text: string }
  | { type: "audio_utterance"; seq: number; sample_rate: number; pcm16_base64: string }
  | { type: "transcript_fix"; seq: number; corrected_text: string }
  | { type: "session_end"; reason: "user" };

export interface SceneInfo {
  id: string;
  title: string;
  place: string;
  user_role: string;
  goal_ko: string;
  required_slots: string[];
  optional_slots: string[];
}

export interface WordOut {
  word: string;
  start: number;
  end: number;
  confidence: number | null;
}

export type ServerMessage =
  | { type: "session_started"; session_id: string; user_id: number; scene: SceneInfo }
  | {
      type: "user_transcript";
      seq: number;
      text: string;
      words: WordOut[];
      low_confidence_spans: string[];
    }
  | {
      type: "scene_state";
      phase: string;
      slots: Record<string, SlotValue>;
      missing_required: string[];
      user_turns: number;
    }
  | {
      type: "npc_reply";
      seq: number;
      text: string;
      action: string;
      source: string;
      latency_ms: number;
    }
  | { type: "npc_audio"; seq: number; format: "wav"; sample_rate: number; data_base64: string }
  | { type: "npc_audio_failed"; seq: number; reason: string }
  | {
      type: "turn_timing";
      seq: number;
      stt_ms: number;
      npc_ms: number;
      llm_ms: number;
      tts_ms: number;
      total_ms: number;
    }
  | { type: "task_result"; success: boolean; reason: string | null }
  | { type: "feedback_pending"; session_id: string }
  | { type: "feedback_ready"; session_id: string; source: string }
  | { type: "error"; code: string; message: string; recoverable: boolean };

// REST: GET /api/sessions/{id}/feedback (backend/app/evaluation/schema.py)
export interface Feedback {
  task_success: boolean;
  grammar_errors: { original: string; corrected: string; type: string; explanation_ko: string }[];
  unnatural_expressions: { original: string; better: string; reason_ko: string }[];
  missed_information: string[];
  recommended_sentences: string[];
  review_items: string[];
  summary: string;
  uncertain_spans: {
    utterance_seq: number;
    word: string;
    confidence: number;
    start: number | null;
    end: number | null;
  }[];
  source: "llm" | "llm_retry" | "default";
  model_id: string | null;
}

// REST: GET /api/users/{id}/review
export interface ReviewData {
  user_id: number;
  nickname: string;
  sessions: { id: string; scene_id: string; started_at: string; success: boolean | null }[];
  review_items: { sentence: string; times: number }[];
  repeated_errors: {
    error_type: string;
    count: number;
    examples: { original: string; corrected: string }[];
  }[];
}
