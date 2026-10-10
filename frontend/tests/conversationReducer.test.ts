import { describe, expect, it } from "vitest";

import {
  conversationReducer,
  initialConversation,
  type ConversationEvent,
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

const started: ServerMessage = { type: "session_started", session_id: "s1", user_id: 7, scene };
const npc = (seq: number, text: string): ServerMessage => ({
  type: "npc_reply",
  seq,
  text,
  action: "greet",
  source: "llm",
  latency_ms: 500,
});
const user = (seq: number, text: string): ServerMessage => ({
  type: "user_transcript",
  seq,
  text,
  words: [],
  low_confidence_spans: [],
});

function run(events: (ServerMessage | ConversationEvent)[]): ConversationState {
  return events.reduce<ConversationState>(
    (state, e) =>
      conversationReducer(state, "msg" in e || e.type === "reset" || e.type === "user_sent"
        ? (e as ConversationEvent)
        : { type: "server", msg: e as ServerMessage }),
    initialConversation,
  );
}

describe("conversationReducer", () => {
  it("builds the chat and order state from server messages", () => {
    const state = run([
      started,
      npc(1, "Hi there!"),
      user(1, "I want hot latte."),
      npc(2, "What size?"),
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
    expect(state.sessionId).toBe("s1");
    expect(state.userId).toBe(7);
  });

  it("shows the NPC as typing until it replies", () => {
    const sent = run([started, npc(1, "Hi"), { type: "user_sent" }]);
    expect(sent.waitingForNpc).toBe(true);
    expect(run([started, npc(1, "Hi"), { type: "user_sent" }, npc(2, "Size?")]).waitingForNpc).toBe(false);
  });

  it("replaces a corrected user line instead of adding a new one", () => {
    const state = run([started, user(1, "I want hot late."), user(1, "I want hot latte.")]);
    expect(state.lines).toHaveLength(1);
    expect(state.lines[0].text).toBe("I want hot latte.");
  });

  it("tracks the result and feedback status", () => {
    const state = run([
      started,
      { type: "task_result", success: true, reason: "completed" },
      { type: "feedback_pending", session_id: "s1" },
    ]);
    expect(state.result).toEqual({ success: true, reason: "completed" });
    expect(state.feedback).toBe("pending");
    expect(conversationReducer(state, { type: "server", msg: { type: "feedback_ready", session_id: "s1", source: "llm" } }).feedback).toBe("ready");
  });

  it("clears an error once the user speaks again", () => {
    const state = run([{ type: "error", code: "x", message: "oops", recoverable: true }, user(1, "Hi")]);
    expect(state.error).toBeNull();
  });

  it("starting a new session resets previous lines", () => {
    const state = run([npc(1, "Old"), started]);
    expect(state.lines).toEqual([]);
    expect(state.scene?.id).toBe("new-york-cafe");
  });

  it("reset returns the initial state", () => {
    const dirty = run([{ type: "task_result", success: false, reason: "user_ended" }]);
    expect(conversationReducer(dirty, { type: "reset" })).toBe(initialConversation);
  });
});
