// Mirrors backend/app/api/messages.py. Keep both in sync.

export type SlotValue = string | number | null;

export type ClientMessage =
  | { type: "session_start"; scene_id?: string }
  | { type: "text_utterance"; seq: number; text: string }
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
  | { type: "session_started"; session_id: string; scene: SceneInfo }
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
  | { type: "npc_reply"; seq: number; text: string; action: string; source: string }
  | { type: "task_result"; success: boolean; reason: string | null }
  | { type: "error"; code: string; message: string; recoverable: boolean };
