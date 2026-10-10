import { describe, expect, it } from "vitest";

import {
  conversationReducer,
  initialConversation,
  type ConversationState,
} from "../src/features/conversation/conversationReducer";
import type { ServerMessage } from "../src/types/messages";

const scene = {
  id: "new-york-cafe",
  title: "A Morning Coffee in Manhattan",
  place: "Café",
  user_role: "Tourist",
  goal_ko: "음료 주문",
  required_slots: ["drink", "size", "temperature"],
  optional_slots: ["milk", "extra_shots"],
};

function run(messages: ServerMessage[]): ConversationState {
  return messages.reduce(
    (state, msg) => conversationReducer(state, { type: "server", msg }),
    initialConversation,
  );
}

describe("conversationReducer", () => {
  it("builds the chat and order state from server messages", () => {
    const state = run([
      { type: "session_started", session_id: "s1", scene },
      { type: "npc_reply", seq: 1, text: "Hi there!", action: "greet", source: "template" },
      { type: "user_transcript", seq: 1, text: "I want hot latte.", words: [], low_confidence_spans: [] },
      { type: "npc_reply", seq: 2, text: "What size?", action: "ask_size", source: "template" },
      {
        type: "scene_state",
        phase: "ordering",
        slots: { drink: "latte", temperature: "hot", size: null },
        missing_required: ["size"],
        user_turns: 1,
      },
    ]);
    expect(state.lines.map((l) => l.speaker)).toEqual(["npc", "user", "npc"]);
    expect(state.phase).toBe("ordering");
    expect(state.slots.drink).toBe("latte");
    expect(state.missingRequired).toEqual(["size"]);
  });

  it("records the task result", () => {
    const state = run([{ type: "task_result", success: true, reason: "completed" }]);
    expect(state.result).toEqual({ success: true, reason: "completed" });
  });

  it("clears an error once the user speaks again", () => {
    const state = run([
      { type: "error", code: "bad_message", message: "oops", recoverable: true },
      { type: "user_transcript", seq: 1, text: "Hi", words: [], low_confidence_spans: [] },
    ]);
    expect(state.error).toBeNull();
  });

  it("starting a new session resets previous lines", () => {
    const state = run([
      { type: "npc_reply", seq: 1, text: "Old", action: "greet", source: "template" },
      { type: "session_started", session_id: "s2", scene },
    ]);
    expect(state.lines).toEqual([]);
    expect(state.scene?.id).toBe("new-york-cafe");
  });

  it("reset returns the initial state", () => {
    const dirty = run([{ type: "task_result", success: false, reason: "user_ended" }]);
    expect(conversationReducer(dirty, { type: "reset" })).toBe(initialConversation);
  });
});
