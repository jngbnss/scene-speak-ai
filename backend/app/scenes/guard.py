"""Checks NPC lines before they reach the user."""

import re
from dataclasses import dataclass, field

from app.scenes.extractor import RuleExtractor
from app.scenes.models import Scene

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]*")


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: list[str] = field(default_factory=list)


def count_sentences(text: str) -> int:
    return sum(1 for s in _SENTENCE_RE.findall(text) if any(c.isalnum() for c in s))


class OutputGuard:
    def __init__(self, scene: Scene, extractor: RuleExtractor | None = None) -> None:
        self.scene = scene
        self.extractor = extractor or RuleExtractor(scene)
        self._forbidden = [re.compile(p, re.IGNORECASE) for p in scene.guard.forbidden_patterns]

    def check(self, text: str, *, allowed_mentions: tuple[str, ...] = ()) -> GuardResult:
        violations = []
        if not text.strip():
            violations.append("empty reply")
        limit = self.scene.npc.max_reply_sentences
        if count_sentences(text) > limit:
            violations.append(f"more than {limit} sentences")
        allowed = {m.lower() for m in allowed_mentions if m}
        for item in self.extractor.unknown_mentions(text):
            if item not in allowed:
                violations.append(f"off-menu item: {item}")
        for pattern in self._forbidden:
            if pattern.search(text):
                violations.append(f"forbidden pattern: {pattern.pattern}")
        return GuardResult(ok=not violations, violations=violations)
