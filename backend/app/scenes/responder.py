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
from app.scenes.extractor import RuleExtractor
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

# Actions whose line restates the order; it must match the Director's state.
RECITING_ACTIONS = frozenset({"confirm_order", "close"})
TEMPERATURE = 0.6
# At the same temperature with a vague complaint, the model returned the identical line
# on every retry in an earlier measurement (D-025).
RETRY_TEMPERATURE = 0.9


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
    # The rejected first line, kept so evaluations can check the guard was right.
    first_text: str | None = None
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


def order_mismatches(extractor: RuleExtractor, text: str, turn: DirectorTurn) -> list[str]:
    """Slot values in an order recap that differ from the Director's state."""
    said = extractor.extract(text).slots
    problems = []
    if turn.action == "confirm_order" and turn.slots.get("drink") and "drink" not in said:
        problems.append("order recap does not name the drink")
    for slot, value in said.items():
        expected = turn.slots.get(slot)
        if slot == "milk" and expected is None:
            expected = "none"
        if expected is not None and value != expected:
            problems.append(f"order recap says {slot}={value}, order has {expected}")
    return problems


def retry_instruction(violations: list[str], scene: Scene, turn: DirectorTurn) -> str:
    """Tells the model exactly what to fix. A bare list of rule names gets the same line."""
    fixes = []
    for v in violations:
        if v.startswith("more than"):
            fixes.append(
                f"Use at most {scene.npc.max_reply_sentences} sentences: merge or drop the "
                "greeting or the list."
            )
        elif v.startswith("off-menu item: "):
            fixes.append(f'Do not say "{v.removeprefix("off-menu item: ")}".')
        elif v.startswith("order recap"):
            fixes.append(f"Say the order exactly as: {turn.context['order_summary']}.")
        elif v.startswith("forbidden pattern") and v.endswith(")"):
            said = v[v.rfind("(") + 1 : -1]
            fixes.append(
                f'Do not say "{said}". You are the barista: no prices, no talk about AI or '
                "English, and never order like a customer."
            )
        elif v == "question after end":
            fixes.append("The order is finished: do not ask anything.")
        else:
            fixes.append(f"Fix: {v}.")
    return (
        "That reply broke the rules. "
        + " ".join(dict.fromkeys(fixes))
        + " Write a new reply with different wording that still does what was asked."
    )


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
        first_text: str | None = None
        latency = 0
        model_id = None
        for attempt in (1, 2):
            try:
                result = self.llm.generate(
                    messages,
                    json_schema=REPLY_SCHEMA,
                    max_tokens=self.max_tokens,
                    temperature=TEMPERATURE if attempt == 1 else RETRY_TEMPERATURE,
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
            if check.ok and turn.action in RECITING_ACTIONS:
                drift = order_mismatches(self.guard.extractor, text, turn)
                if drift:
                    check = GuardResult(ok=False, violations=drift)
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
                first_violations = check.violations
                first_text = text
                messages = [
                    *messages,
                    ChatMessage(role="assistant", content=result.text),
                    ChatMessage(
                        role="system",
                        content=retry_instruction(check.violations, self.scene, turn),
                    ),
                ]
        text = render_fallback(self.scene, turn)
        return NpcReply(
            text=text,
            source="template_fallback",
            guard=self.guard.check(text, allowed_mentions=allowed),
            attempts=2 if first_violations else 1,
            first_violations=first_violations,
            first_text=first_text,
            llm_latency_ms=latency,
            model_id=model_id,
        )
