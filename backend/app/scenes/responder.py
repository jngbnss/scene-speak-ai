"""Turns a Director action into the NPC's line.

``TemplateResponder`` uses the scene's fallback lines. ``LLMResponder`` asks the LLM to
phrase the action, checks the line with the output guard, retries once, and falls back to
the template so the NPC always has something safe to say.
"""

import logging
import string
from dataclasses import dataclass, field
from typing import Protocol

from app.ai.types import AdapterError, ChatMessage, LLMAdapter
from app.scenes.director import DirectorTurn
from app.scenes.guard import GuardResult, OutputGuard
from app.scenes.models import Scene
from app.scenes.prompts import npc_messages

log = logging.getLogger(__name__)

KNOWN_PLACEHOLDERS = frozenset(
    {"menu_list", "sizes", "order_summary", "drink_name", "allowed_temperatures", "item"}
)

REPLY_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
}

History = list[tuple[str, str]]  # (speaker, text), speaker is "user" or "npc"


def placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def render_fallback(scene: Scene, turn: DirectorTurn) -> str:
    return scene.actions[turn.action].fallback.format_map(turn.context)


@dataclass(frozen=True)
class NpcReply:
    text: str
    # "template" | "llm" | "llm_retry" | "template_fallback"
    source: str
    guard: GuardResult
    attempts: int = 0
    first_violations: list[str] = field(default_factory=list)
    llm_latency_ms: int = 0
    model_id: str | None = None


class Responder(Protocol):
    def reply(self, turn: DirectorTurn, history: History) -> NpcReply: ...


class TemplateResponder:
    def __init__(self, scene: Scene, guard: OutputGuard) -> None:
        self.scene = scene
        self.guard = guard

    def reply(self, turn: DirectorTurn, history: History) -> NpcReply:
        text = render_fallback(self.scene, turn)
        result = self.guard.check(text, allowed_mentions=(turn.context.get("item", ""),))
        return NpcReply(text=text, source="template", guard=result)


class LLMResponder:
    def __init__(
        self, scene: Scene, guard: OutputGuard, llm: LLMAdapter, *, max_tokens: int = 80
    ) -> None:
        self.scene = scene
        self.guard = guard
        self.llm = llm
        self.max_tokens = max_tokens

    def reply(self, turn: DirectorTurn, history: History) -> NpcReply:
        allowed = (turn.context.get("item", ""),)
        messages = npc_messages(self.scene, turn, history)
        first_violations: list[str] = []
        latency = 0
        model_id = None
        for attempt in (1, 2):
            try:
                result = self.llm.generate(
                    messages, json_schema=REPLY_SCHEMA, max_tokens=self.max_tokens
                )
            except AdapterError as exc:
                log.warning("LLM failed on %s: %s", turn.action, exc)
                break
            latency += result.latency_ms
            model_id = result.model_id
            text = str((result.parsed or {}).get("reply", "")).strip()
            check = self.guard.check(text, allowed_mentions=allowed)
            if turn.ended and "?" in text:
                # The scene is over; a question here would leave the user hanging.
                check = GuardResult(ok=False, violations=[*check.violations, "question after end"])
            if check.ok:
                return NpcReply(
                    text=text,
                    source="llm" if attempt == 1 else "llm_retry",
                    guard=check,
                    attempts=attempt,
                    first_violations=first_violations,
                    llm_latency_ms=latency,
                    model_id=model_id,
                )
            if attempt == 1:
                first_violations = check.violations
                messages = [
                    *messages,
                    ChatMessage(role="assistant", content=result.text),
                    ChatMessage(
                        role="system",
                        content=(
                            "That reply broke the rules: "
                            + "; ".join(check.violations)
                            + ". Write a new reply that follows every rule."
                        ),
                    ),
                ]
        text = render_fallback(self.scene, turn)
        return NpcReply(
            text=text,
            source="template_fallback",
            guard=self.guard.check(text, allowed_mentions=allowed),
            attempts=2 if first_violations else 1,
            first_violations=first_violations,
            llm_latency_ms=latency,
            model_id=model_id,
        )
