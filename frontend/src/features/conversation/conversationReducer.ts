import type { SceneInfo, ServerMessage, SlotValue } from "../../types/messages";

export interface ChatLine {
  id: string;
  speaker: "npc" | "user";
  seq: number;
  text: string;
  action?: string;
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
  error: string | null;
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
      const lines = exists
        ? state.lines.map((l) => (l.id === id ? { ...l, text: msg.text } : l))
        : [...state.lines, { id, speaker: "user" as const, seq: msg.seq, text: msg.text }];
      return { ...state, error: null, lines };
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
    case "feedback_pending":
      return { ...state, feedback: "pending" };
    case "feedback_ready":
      return { ...state, feedback: "ready" };
    case "error":
      return { ...state, waitingForNpc: false, error: msg.message };
  }
}
