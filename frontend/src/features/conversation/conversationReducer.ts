import type { SceneInfo, ServerMessage, SlotValue } from "../../types/messages";

export interface ChatLine {
  id: string;
  speaker: "npc" | "user";
  text: string;
  action?: string;
}

export interface ConversationState {
  scene: SceneInfo | null;
  lines: ChatLine[];
  phase: string;
  slots: Record<string, SlotValue>;
  missingRequired: string[];
  result: { success: boolean; reason: string | null } | null;
  error: string | null;
}

export const initialConversation: ConversationState = {
  scene: null,
  lines: [],
  phase: "greeting",
  slots: {},
  missingRequired: [],
  result: null,
  error: null,
};

export type ConversationEvent = { type: "reset" } | { type: "server"; msg: ServerMessage };

export function conversationReducer(
  state: ConversationState,
  event: ConversationEvent,
): ConversationState {
  if (event.type === "reset") return initialConversation;
  const msg = event.msg;
  switch (msg.type) {
    case "session_started":
      return { ...initialConversation, scene: msg.scene };
    case "user_transcript":
      return {
        ...state,
        error: null,
        lines: [...state.lines, { id: `u${msg.seq}`, speaker: "user", text: msg.text }],
      };
    case "npc_reply":
      return {
        ...state,
        lines: [
          ...state.lines,
          { id: `n${msg.seq}`, speaker: "npc", text: msg.text, action: msg.action },
        ],
      };
    case "scene_state":
      return { ...state, phase: msg.phase, slots: msg.slots, missingRequired: msg.missing_required };
    case "task_result":
      return { ...state, result: { success: msg.success, reason: msg.reason } };
    case "error":
      return { ...state, error: msg.message };
  }
}
