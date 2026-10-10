import type { SceneInfo, ServerMessage, SlotValue } from "../../types/messages";

export interface ChatLine {
  id: string;
  speaker: "npc" | "user";
  seq: number;
  text: string;
  action?: string;
  /** Words the speech recognizer was unsure about. */
  uncertain?: string[];
  spoken?: boolean;
}

export type FeedbackStatus = "none" | "pending" | "ready";

export interface ConversationState {
  scene: SceneInfo | null;
  sessionId: string | null;
  userId: number | null;
  lines: ChatLine[];
  phase: string;
  slots: Record<string, SlotValue>;
  missingRequired: string[];
  result: { success: boolean; reason: string | null } | null;
  feedback: FeedbackStatus;
  waitingForNpc: boolean;
  timing: TurnTiming | null;
  error: string | null;
}

export interface TurnTiming {
  stt_ms: number;
  npc_ms: number;
  tts_ms: number;
  total_ms: number;
}

export const initialConversation: ConversationState = {
  scene: null,
  sessionId: null,
  userId: null,
  lines: [],
  phase: "greeting",
  slots: {},
  missingRequired: [],
  result: null,
  feedback: "none",
  waitingForNpc: false,
  timing: null,
  error: null,
};

export type ConversationEvent =
  | { type: "reset" }
  | { type: "user_sent" }
  | { type: "server"; msg: ServerMessage };

export function conversationReducer(
  state: ConversationState,
  event: ConversationEvent,
): ConversationState {
  if (event.type === "reset") return initialConversation;
  if (event.type === "user_sent") return { ...state, waitingForNpc: true, error: null };
  const msg = event.msg;
  switch (msg.type) {
    case "session_started":
      return {
        ...initialConversation,
        scene: msg.scene,
        sessionId: msg.session_id,
        userId: msg.user_id,
        waitingForNpc: true,
      };
    case "user_transcript": {
      const id = `u${msg.seq}`;
      const exists = state.lines.some((l) => l.id === id);
      const spoken = msg.words.length > 0;
      const uncertain = msg.low_confidence_spans;
      const lines = exists
        ? state.lines.map((l) =>
            // A typed correction replaces the recognized words.
            l.id === id ? { ...l, text: msg.text, uncertain: spoken ? uncertain : [] } : l,
          )
        : [
            ...state.lines,
            { id, speaker: "user" as const, seq: msg.seq, text: msg.text, uncertain, spoken },
          ];
      return { ...state, error: null, waitingForNpc: exists ? state.waitingForNpc : true, lines };
    }
    case "npc_reply":
      return {
        ...state,
        waitingForNpc: false,
        lines: [
          ...state.lines,
          { id: `n${msg.seq}`, speaker: "npc", seq: msg.seq, text: msg.text, action: msg.action },
        ],
      };
    case "scene_state":
      return {
        ...state,
        waitingForNpc: false,
        phase: msg.phase,
        slots: msg.slots,
        missingRequired: msg.missing_required,
      };
    case "task_result":
      return { ...state, result: { success: msg.success, reason: msg.reason } };
    case "turn_timing":
      return {
        ...state,
        timing: {
          stt_ms: msg.stt_ms,
          npc_ms: msg.npc_ms,
          tts_ms: msg.tts_ms,
          total_ms: msg.total_ms,
        },
      };
    case "npc_audio":
    case "npc_audio_failed":
      return state;
    case "feedback_pending":
      return { ...state, feedback: "pending" };
    case "feedback_ready":
      return { ...state, feedback: "ready" };
    case "error":
      return { ...state, waitingForNpc: false, error: msg.message };
  }
}
