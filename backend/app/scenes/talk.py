"""Mission talks: short task conversations with world NPCs (hot dog stand, directions, ...).

The café scene needs a slot-filling Director. Most other street conversations don't: the
learner just has to get a few things done ("ask the way", "say thanks"). A talk scene lists
those steps with regular expressions, so progress and success are decided by rules, never
by the LLM (D-030). The LLM only voices the NPC, limited to the facts in the scene file,
and every line passes a guard with one retry and a template fallback, like the café NPC.

A free chat with a passer-by (scenes/people/*.yaml, D-032) is the same kind of scene in
"chat" mode: the steps are conversation goals (greet, introduce yourself, ask a question,
say goodbye), the talk does not end when they are all done, and it ends when the learner
says goodbye. The goals are met if they did every step by then.
"""

import logging
import re
import uuid
from typing import Literal

from app.ai.types import AdapterError, ChatMessage, LLMAdapter
from app.scenes.conversation import TurnResult
from app.scenes.director import DirectorTurn
from app.scenes.guard import GuardResult, count_sentences
from app.scenes.models import Goal, Guard, Learning, Npc, Setting, _Strict
from app.scenes.responder import REPLY_SCHEMA, RETRY_TEMPERATURE, TEMPERATURE, NpcReply

log = logging.getLogger(__name__)

HISTORY_LINES = 8
# "$4", "$2.90": the NPC may only quote prices that appear in the scene facts.
_MONEY = re.compile(r"\$\s?(\d+(?:\.\d\d)?)")


class TalkStep(_Strict):
    id: str
    description_ko: str
    # Any match in a user line completes the step (case-insensitive regular expressions).
    patterns: list[str]
    # What the NPC does to invite this step, told to the LLM.
    npc_hint: str
    # Template NPC line inviting this step when there is no LLM or the guard rejects it.
    fallback: str


class TalkScene(_Strict):
    id: str
    version: int
    locale: str
    kind: Literal["talk"]
    # "mission": ends as soon as every step is done. "chat": free talk, ends on goodbye.
    mode: Literal["mission", "chat"] = "mission"
    title: str
    setting: Setting
    npc: Npc
    user_role: str
    goal: Goal
    # The only things the NPC may state as fact (prices, directions, times).
    facts: list[str]
    opening: str
    steps: list[TalkStep]
    closing: str
    unfinished_closing: str
    goodbye_patterns: list[str]
    max_user_turns: int
    hotwords: list[str]
    guard: Guard
    learning: Learning


class TalkGuard:
    def __init__(self, scene: TalkScene) -> None:
        self.scene = scene
        self._forbidden = [re.compile(p, re.IGNORECASE) for p in scene.guard.forbidden_patterns]
        self._fact_amounts = {a for fact in scene.facts for a in _MONEY.findall(fact)}

    def check(self, text: str, *, closing: bool = False) -> GuardResult:
        violations = []
        if not text.strip():
            violations.append("empty reply")
        limit = self.scene.npc.max_reply_sentences
        if count_sentences(text) > limit:
            violations.append(f"more than {limit} sentences")
        for pattern in self._forbidden:
            found = pattern.search(text)
            if found:
                violations.append(f"forbidden pattern: {pattern.pattern} ({found.group(0)})")
        for amount in _MONEY.findall(text):
            if amount not in self._fact_amounts:
                violations.append(f"price not in the facts: ${amount}")
        if closing and "?" in text:
            violations.append("question after the conversation ended")
        return GuardResult(ok=not violations, violations=violations)


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


class TalkSession:
    """Same surface as ConversationSession (start / handle_text / end / ended)."""

    def __init__(
        self, scene: TalkScene, llm: LLMAdapter | None = None, session_id: str | None = None
    ) -> None:
        self.id = session_id or uuid.uuid4().hex
        self.scene = scene
        self.llm = llm
        self.guard = TalkGuard(scene)
        self.done: set[str] = set()
        self.user_turns = 0
        self.phase = "greeting"
        self.end_reason: str | None = None
        self.transcript: list[tuple[str, str]] = []
        self.replies: list[NpcReply] = []

    # ----- state ------------------------------------------------------------------------

    @property
    def ended(self) -> bool:
        return self.phase in ("completed", "cancelled")

    @property
    def success(self) -> bool:
        return self.phase == "completed"

    @property
    def missing_required(self) -> list[str]:
        return [s.id for s in self.scene.steps if s.id not in self.done]

    @property
    def missing_ko(self) -> list[str]:
        return [s.description_ko for s in self.scene.steps if s.id not in self.done]

    def _next_step(self):
        return next((s for s in self.scene.steps if s.id not in self.done), None)

    def _turn(self, action: str) -> DirectorTurn:
        ended = self.ended
        return DirectorTurn(
            action=action,
            phase=self.phase,
            context={},
            extraction=None,
            slots={s.id: ("done" if s.id in self.done else None) for s in self.scene.steps},
            missing_required=self.missing_required,
            ended=ended,
            success=self.success if ended else None,
            end_reason=self.end_reason,
        )

    # ----- turns ------------------------------------------------------------------------

    def start(self) -> TurnResult:
        reply = NpcReply(text=self.scene.opening, source="template", guard=GuardResult(True))
        return self._record(TurnResult(self._turn("greet"), reply))

    def handle_text(self, text: str) -> TurnResult:
        self.transcript.append(("user", text))
        self.user_turns += 1
        self.phase = "talking"
        newly = [
            s.id for s in self.scene.steps if s.id not in self.done and _matches(s.patterns, text)
        ]
        self.done.update(newly)

        if self.scene.mode == "chat":
            action = self._chat_action(text)
        elif not self.missing_required:
            self.phase, self.end_reason = "completed", "completed"
            action = "close"
        elif _matches(self.scene.goodbye_patterns, text):
            self.phase, self.end_reason = "cancelled", "user_ended"
            action = "end_unfinished"
        elif self.user_turns >= self.scene.max_user_turns:
            self.phase, self.end_reason = "cancelled", "max_user_turns"
            action = "end_unfinished"
        else:
            action = "respond"
        return self._record(TurnResult(self._turn(action), self._reply(action)))

    def _chat_action(self, text: str) -> str:
        if _matches(self.scene.goodbye_patterns, text):
            self.end_reason = "user_ended"
        elif self.user_turns >= self.scene.max_user_turns:
            self.end_reason = "max_user_turns"
        else:
            return "respond"
        if self.missing_required:
            self.phase = "cancelled"
            return "end_unfinished"
        self.phase = "completed"
        return "close"

    def end(self) -> TurnResult:
        if self.ended:
            return TurnResult(self._turn("end_unfinished"), None)
        self.phase, self.end_reason = "cancelled", "user_ended"
        return self._record(TurnResult(self._turn("end_unfinished"), self._reply("end_unfinished")))

    def _record(self, result: TurnResult) -> TurnResult:
        if result.reply is not None:
            self.transcript.append(("npc", result.reply.text))
            self.replies.append(result.reply)
        return result

    # ----- NPC lines --------------------------------------------------------------------

    def _fallback(self, action: str) -> str:
        if action == "close":
            return self.scene.closing
        if action == "end_unfinished":
            return self.scene.unfinished_closing
        step = self._next_step()
        return step.fallback if step else self.scene.closing

    def _instruction(self, action: str) -> str:
        if action == "close" and self.scene.mode == "chat":
            return "The visitor is saying goodbye. Say a short, warm goodbye. No questions."
        if action == "close":
            return (
                "The visitor has done everything they came for. Reply briefly to their last "
                "line and say a friendly goodbye. Do not ask a question."
            )
        if action == "end_unfinished":
            return "The visitor is leaving. Say a short, friendly goodbye. Do not ask a question."
        step = self._next_step()
        hint = f" Then, if it fits naturally, {step.npc_hint}" if step else ""
        if self.scene.mode == "chat":
            return (
                "This is friendly small talk. Reply to their last line in character, and "
                f"sometimes ask them a simple question back.{hint}"
            )
        return f"Reply to the visitor's last line using only the facts above.{hint}"

    def _facts_heading(self) -> str:
        if self.scene.mode == "chat":
            return (
                "Facts about you (stay consistent with them; you may add small everyday "
                "details, but never prices or addresses):"
            )
        return (
            "Facts you may use (never invent prices, places, times or names that are not listed):"
        )

    def messages(self, action: str, retry_note: str = "") -> list[ChatMessage]:
        s, npc = self.scene, self.scene.npc
        facts = "\n".join(f"- {f}" for f in s.facts)
        system = f"""You are a {npc.role} at {s.setting.place} in New York. {npc.persona}
{s.setting.description_for_llm.strip()}
The other person is a {s.user_role} who is practicing English.

{self._facts_heading()}
{facts}

Rules:
- Speak simple, natural spoken English (CEFR A2-B1).
- At most {npc.max_reply_sentences} short sentences.
- Stay in your role. Never say you are an AI, never teach or correct English.
- You are the {npc.role}; do not talk as if you were the visitor.
- {self._instruction(action)}
Return JSON: {{"reply": "<your line>"}}"""
        if retry_note:
            system += f"\nYour previous line was rejected: {retry_note}. Fix that."
        history = [
            ChatMessage(role="user" if who == "user" else "assistant", content=text)
            for who, text in self.transcript[-HISTORY_LINES:]
        ]
        return [ChatMessage(role="system", content=system), *history]

    def _reply(self, action: str) -> NpcReply:
        closing = action in ("close", "end_unfinished")
        if self.llm is None:
            text = self._fallback(action)
            return NpcReply(text=text, source="template", guard=self.guard.check(text))
        first_violations: list[str] = []
        first_text = None
        latency = 0
        model_id = None
        for attempt in (1, 2):
            note = "; ".join(first_violations)
            try:
                result = self.llm.generate(
                    self.messages(action, note),
                    json_schema=REPLY_SCHEMA,
                    max_tokens=96,
                    temperature=TEMPERATURE if attempt == 1 else RETRY_TEMPERATURE,
                )
            except AdapterError as exc:
                log.warning("talk NPC LLM failed: %s", exc)
                break
            latency += result.latency_ms
            model_id = result.model_id
            text = str((result.parsed or {}).get("reply", "")).strip()
            check = self.guard.check(text, closing=closing)
            if check.ok:
                return NpcReply(
                    text=text,
                    source="llm" if attempt == 1 else "llm_retry",
                    guard=check,
                    attempts=attempt,
                    first_violations=first_violations,
                    first_text=first_text,
                    llm_latency_ms=latency,
                    model_id=model_id,
                )
            if attempt == 1:
                first_violations, first_text = check.violations, text
        text = self._fallback(action)
        return NpcReply(
            text=text,
            source="template_fallback",
            guard=self.guard.check(text, closing=closing),
            attempts=2,
            first_violations=first_violations,
            first_text=first_text,
            llm_latency_ms=latency,
            model_id=model_id,
        )
