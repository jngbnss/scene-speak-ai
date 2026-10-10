import json
import time
from collections import deque

from app.ai.types import ChatMessage, LLMResult


def default_from_schema(schema: dict) -> object:
    """Builds the smallest value that satisfies a simple JSON schema."""
    kind = schema.get("type")
    if isinstance(kind, list):
        if "null" in kind:
            return None
        kind = kind[0]
    if kind == "object":
        props = schema.get("properties", {})
        return {name: default_from_schema(sub) for name, sub in props.items()}
    return {"string": "", "integer": 0, "number": 0, "boolean": False, "array": []}.get(kind)


class MockLLM:
    """Replays scripted responses in order, then falls back to schema defaults."""

    model_id = "mock-llm"

    def __init__(self, responses: list[str | dict] | None = None) -> None:
        self._responses: deque[str | dict] = deque(responses or [])
        self.calls: list[list[ChatMessage]] = []

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict | None = None,
        max_tokens: int = 128,
        temperature: float = 0.6,
    ) -> LLMResult:
        started = time.perf_counter()
        self.calls.append(messages)
        if self._responses:
            raw = self._responses.popleft()
        elif json_schema is not None:
            raw = default_from_schema(json_schema)
        else:
            raw = ""
        text = raw if isinstance(raw, str) else json.dumps(raw)
        parsed = None
        if json_schema is not None:
            parsed = raw if isinstance(raw, dict) else json.loads(raw)
        return LLMResult(
            text=text,
            parsed=parsed,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model_id=self.model_id,
        )
