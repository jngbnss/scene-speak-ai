"""AI response contracts, checked in CI without any model (fixture-based).

Each JSON Schema sent to Ollama (`format=`) must be a valid schema without $ref/$defs
(Ollama's grammar conversion does not follow them), accept the recorded valid responses,
reject the invalid ones, and the code that consumes the response must accept every
response the schema accepts.
"""

import json
from pathlib import Path

import jsonschema
import pytest

from app.evaluation.schema import LLM_FEEDBACK_SCHEMA, LLMFeedback
from app.scenes.llm_assist import EXTRACTION_SCHEMA, LLMAssist
from app.scenes.responder import REPLY_SCHEMA

FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"
SCHEMAS = {
    "npc_reply": REPLY_SCHEMA,
    "extraction": EXTRACTION_SCHEMA,
    "feedback": LLM_FEEDBACK_SCHEMA,
}


def _load(name: str, kind: str) -> list:
    return json.loads((FIXTURES / f"{name}.{kind}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_valid_and_self_contained(name):
    schema = SCHEMAS[name]
    jsonschema.Draft202012Validator.check_schema(schema)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text


@pytest.mark.parametrize("name", SCHEMAS)
def test_valid_responses_pass(name):
    validator = jsonschema.Draft202012Validator(SCHEMAS[name])
    for response in _load(name, "valid"):
        assert not list(validator.iter_errors(response)), response


@pytest.mark.parametrize("name", SCHEMAS)
def test_invalid_responses_fail(name):
    validator = jsonschema.Draft202012Validator(SCHEMAS[name])
    for response in _load(name, "invalid"):
        assert list(validator.iter_errors(response)), f"schema accepted {response}"


def test_feedback_consumer_accepts_every_valid_response():
    for response in _load("feedback", "valid"):
        LLMFeedback.model_validate(response)


def test_extraction_consumer_accepts_every_valid_response(scene, extractor):
    assist = LLMAssist(scene, extractor, llm=None)
    for response in _load("extraction", "valid"):
        assist.to_extraction(response)


def test_reply_schema_requires_exactly_what_the_responder_reads():
    assert REPLY_SCHEMA["required"] == ["reply"]
