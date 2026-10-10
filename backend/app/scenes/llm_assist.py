"""LLM fallback for utterances the rule extractor did not understand.

The LLM's answer is never trusted directly: every value is mapped back through the
scene's alias lists, so only real menu ids can reach the order state.
"""

import logging
import re

from app.ai.types import AdapterError, LLMAdapter
from app.scenes.extractor import Extraction, RuleExtractor
from app.scenes.models import Scene
from app.scenes.prompts import extraction_messages

log = logging.getLogger(__name__)

_NULLABLE_STR = {"type": ["string", "null"]}
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "drink": _NULLABLE_STR,
        "size": _NULLABLE_STR,
        "temperature": _NULLABLE_STR,
        "milk": _NULLABLE_STR,
        "extra_shots": {"type": ["integer", "null"]},
        "requested_item_not_on_menu": _NULLABLE_STR,
        "intent": {
            "type": "string",
            "enum": ["order", "modify", "confirm", "deny", "cancel", "question", "other"],
        },
    },
    "required": [
        "drink", "size", "temperature", "milk", "extra_shots",
        "requested_item_not_on_menu", "intent",
    ],
}  # fmt: skip

_LATIN = re.compile(r"[A-Za-z]")


class LLMAssist:
    def __init__(self, scene: Scene, extractor: RuleExtractor, llm: LLMAdapter) -> None:
        self.scene = scene
        self.extractor = extractor
        self.llm = llm
        self.calls = 0

    def __call__(self, text: str) -> Extraction | None:
        # The point is practicing English, so non-English input is not interpreted.
        if not _LATIN.search(text):
            return None
        self.calls += 1
        try:
            result = self.llm.generate(
                extraction_messages(self.scene, text),
                json_schema=EXTRACTION_SCHEMA,
                max_tokens=120,
                temperature=0.0,
            )
        except AdapterError as exc:
            log.warning("LLM extraction failed: %s", exc)
            return None
        return self.to_extraction(result.parsed or {})

    def to_extraction(self, data: dict) -> Extraction:
        ext = Extraction(source="llm")
        for slot in ("drink", "size", "temperature", "milk"):
            value = data.get(slot)
            if isinstance(value, str) and value.strip():
                mapped = self.extractor.extract(value).slots.get(slot)
                if mapped is not None:
                    ext.slots[slot] = mapped
        shots = data.get("extra_shots")
        if isinstance(shots, int) and 0 <= shots <= self.scene.menu.extra_shots.max:
            ext.slots["extra_shots"] = shots

        item = data.get("requested_item_not_on_menu")
        if isinstance(item, str) and item.strip():
            item_ext = self.extractor.extract(item)
            if "drink" not in item_ext.slots or item_ext.unknown_item:
                ext.unknown_item = item.strip().lower()
        drink = data.get("drink")
        unmapped_drink = isinstance(drink, str) and drink.strip() and "drink" not in ext.slots
        if ext.unknown_item is None and unmapped_drink:
            # The LLM named a drink that does not map to the menu.
            ext.unknown_item = str(drink).strip().lower()

        intent = data.get("intent")
        if intent in ("confirm", "deny", "cancel"):
            ext.intents.add(intent)
        return ext
