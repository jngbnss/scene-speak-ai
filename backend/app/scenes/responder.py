"""Turns a Director action into the NPC's line.

Phase 1 uses the scene's fallback templates only. An LLM-backed responder will implement
the same interface in Phase 2 and fall back to ``render_fallback`` when it fails.
"""

import string
from dataclasses import dataclass
from typing import Protocol

from app.scenes.director import DirectorTurn
from app.scenes.guard import GuardResult, OutputGuard
from app.scenes.models import Scene

KNOWN_PLACEHOLDERS = frozenset(
    {"menu_list", "sizes", "order_summary", "drink_name", "allowed_temperatures", "item"}
)


def placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def render_fallback(scene: Scene, turn: DirectorTurn) -> str:
    return scene.actions[turn.action].fallback.format_map(turn.context)


@dataclass(frozen=True)
class NpcReply:
    text: str
    source: str  # "template" | "llm" | "llm_retry"
    guard: GuardResult


class Responder(Protocol):
    def reply(self, turn: DirectorTurn) -> NpcReply: ...


class TemplateResponder:
    def __init__(self, scene: Scene, guard: OutputGuard) -> None:
        self.scene = scene
        self.guard = guard

    def reply(self, turn: DirectorTurn) -> NpcReply:
        text = render_fallback(self.scene, turn)
        result = self.guard.check(text, allowed_mentions=(turn.context.get("item", ""),))
        return NpcReply(text=text, source="template", guard=result)
