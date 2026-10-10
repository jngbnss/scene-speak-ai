"""Ollama chat adapter (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

import json
import time

import httpx

from app.ai.types import AdapterError, ChatMessage, LLMResult


class OllamaLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        think: bool | None = False,
        keep_alive: str = "30m",
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.model_id = f"ollama:{model}"
        self._think = think
        self._keep_alive = keep_alive
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_s)

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict | None = None,
        max_tokens: int = 128,
        temperature: float = 0.6,
    ) -> LLMResult:
        body: dict = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if self._think is not None:
            body["think"] = self._think
        if json_schema is not None:
            body["format"] = json_schema

        started = time.perf_counter()
        try:
            response = self._client.post("/api/chat", json=body)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise AdapterError(f"Ollama request failed: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = data.get("message", {}).get("content", "")
        parsed = None
        if json_schema is not None:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise AdapterError(f"Ollama returned invalid JSON: {text[:200]!r}") from exc
            if not isinstance(parsed, dict):
                raise AdapterError("Ollama returned JSON that is not an object")
        return LLMResult(
            text=text,
            parsed=parsed,
            latency_ms=latency_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            model_id=self.model_id,
        )

    def warm_up(self) -> None:
        """Loads the model into memory so the first user turn is not slow."""
        self.generate([ChatMessage(role="user", content="Hi")], max_tokens=1)
