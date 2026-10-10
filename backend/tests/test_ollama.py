import json

import httpx
import pytest

from app.ai.llm.ollama import OllamaLLM
from app.ai.types import AdapterError, ChatMessage

MSGS = [ChatMessage(role="user", content="I want a latte")]


def _llm(handler) -> tuple[OllamaLLM, list[dict]]:
    seen: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return handler(request)

    client = httpx.Client(base_url="http://ollama", transport=httpx.MockTransport(wrapped))
    return OllamaLLM("http://ollama", "qwen3:8b", client=client), seen


def _ok(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"message": {"content": content}, "prompt_eval_count": 42, "eval_count": 7}
    )


def test_request_body_and_parsed_result():
    llm, seen = _llm(lambda r: _ok('{"reply": "Sure!"}'))
    schema = {"type": "object", "properties": {"reply": {"type": "string"}}}
    result = llm.generate(MSGS, json_schema=schema, max_tokens=50, temperature=0.1)
    body = seen[0]
    assert body["model"] == "qwen3:8b"
    assert body["think"] is False
    assert body["stream"] is False
    assert body["format"] == schema
    assert body["options"] == {"num_predict": 50, "temperature": 0.1}
    assert body["messages"] == [{"role": "user", "content": "I want a latte"}]
    assert result.parsed == {"reply": "Sure!"}
    assert (result.prompt_tokens, result.completion_tokens) == (42, 7)
    assert result.model_id == "ollama:qwen3:8b"


def test_plain_text_without_schema():
    llm, seen = _llm(lambda r: _ok("Hello"))
    result = llm.generate(MSGS)
    assert "format" not in seen[0]
    assert result.text == "Hello" and result.parsed is None


def test_think_flag_can_be_omitted():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return _ok("x")

    client = httpx.Client(base_url="http://o", transport=httpx.MockTransport(handler))
    OllamaLLM("http://o", "llama3", think=None, client=client).generate(MSGS)
    assert "think" not in seen[0]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "model not found"}),
        _ok("not json"),
        _ok("[1, 2]"),
    ],
)
def test_failures_raise_adapter_error(response):
    llm, _ = _llm(lambda r: response)
    with pytest.raises(AdapterError):
        llm.generate(MSGS, json_schema={"type": "object"})


def test_connection_error_is_adapter_error():
    def boom(request):
        raise httpx.ConnectError("refused")

    llm, _ = _llm(boom)
    with pytest.raises(AdapterError):
        llm.generate(MSGS)
