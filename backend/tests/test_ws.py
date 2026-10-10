import pytest
from fastapi.testclient import TestClient

from app.ai.llm.mock import MockLLM
from app.main import app

pytestmark = pytest.mark.usefixtures("services")


@pytest.fixture
def ws():
    with TestClient(app) as client, client.websocket_connect("/ws/session") as socket:
        yield socket


def _until(ws, msg_type: str) -> dict:
    for _ in range(10):
        msg = ws.receive_json()
        if msg["type"] == msg_type:
            return msg
    raise AssertionError(f"no {msg_type} message")


def test_health():
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["providers"]["llm"] == "mock"


def test_full_order_over_websocket(ws):
    ws.send_json({"type": "session_start"})
    started = ws.receive_json()
    assert started["type"] == "session_started"
    assert started["scene"]["required_slots"] == ["drink", "size", "temperature"]
    greet = ws.receive_json()
    assert greet["type"] == "npc_reply" and greet["action"] == "greet"
    assert ws.receive_json()["phase"] == "greeting"

    lines = ["I want hot latte.", "Large, please. And can I have oat milk?", "Yes, that's all."]
    for seq, text in enumerate(lines, start=1):
        ws.send_json({"type": "text_utterance", "seq": seq, "text": text})
        transcript = ws.receive_json()
        assert transcript == {
            "type": "user_transcript",
            "seq": seq,
            "text": text,
            "words": [],
            "low_confidence_spans": [],
        }
        reply = ws.receive_json()
        assert reply["type"] == "npc_reply"
        state = ws.receive_json()
        assert state["type"] == "scene_state"

    assert reply["action"] == "close"
    assert state["phase"] == "completed"
    assert ws.receive_json() == {"type": "task_result", "success": True, "reason": "completed"}


def test_text_before_start_is_an_error(ws):
    ws.send_json({"type": "text_utterance", "seq": 1, "text": "Hi"})
    assert _until(ws, "error")["code"] == "no_session"


def test_bad_message(ws):
    ws.send_text("not json")
    assert _until(ws, "error")["code"] == "bad_message"
    ws.send_json({"type": "unknown"})
    assert _until(ws, "error")["code"] == "bad_message"


def test_unknown_scene(ws):
    ws.send_json({"type": "session_start", "scene_id": "paris-bakery"})
    assert _until(ws, "error")["code"] == "scene_not_found"


def test_session_end_reports_failure(ws):
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json({"type": "text_utterance", "seq": 1, "text": "A latte"})
    _until(ws, "scene_state")
    ws.send_json({"type": "session_end"})
    reply = _until(ws, "npc_reply")
    assert reply["action"] == "acknowledge_cancel"
    result = _until(ws, "task_result")
    assert result == {"type": "task_result", "success": False, "reason": "user_ended"}


def test_text_after_end_is_rejected(ws):
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json({"type": "text_utterance", "seq": 1, "text": "cancel"})
    _until(ws, "task_result")
    ws.send_json({"type": "text_utterance", "seq": 2, "text": "A latte"})
    assert _until(ws, "error")["code"] == "session_ended"


def _finish_order(ws, nickname="mina") -> dict:
    ws.send_json({"type": "session_start", "nickname": nickname})
    started = _until(ws, "session_started")
    _until(ws, "scene_state")
    lines = ["I want hot latte.", "Large, please. And can I have oat milk?", "Yes, that's all."]
    for seq, text in enumerate(lines, start=1):
        ws.send_json({"type": "text_utterance", "seq": seq, "text": text})
        _until(ws, "scene_state")
    return started


def test_feedback_is_generated_and_served(ws, services):
    services.llm = MockLLM(
        [
            {
                "lines": [
                    {
                        "line": "I want hot latte.",
                        "grammar_ok": False,
                        "corrected": "I want a hot latte.",
                        "error_type": "article",
                        "explanation_ko": "관사",
                        "more_natural": "",
                        "reason_ko": "",
                    }
                ],
                "recommended_sentences": [],
                "review_items": ["Can I get a hot latte?"],
                "summary": "잘했어요.",
            }
        ]
    )
    started = _finish_order(ws)
    assert _until(ws, "task_result")["success"] is True
    assert _until(ws, "feedback_pending")["session_id"] == started["session_id"]
    ready = _until(ws, "feedback_ready")
    assert ready["source"] == "llm"

    with TestClient(app) as client:
        fb = client.get(f"/api/sessions/{ready['session_id']}/feedback").json()
        review = client.get(f"/api/users/{started['user_id']}/review").json()
        assert client.get("/api/sessions/nope/feedback").status_code == 404
        assert client.get("/api/users/999/review").status_code == 404
    assert fb["task_success"] is True
    assert fb["grammar_errors"][0]["type"] == "article"
    assert review["nickname"] == "mina"
    assert review["review_items"][0]["sentence"] == "Can I get a hot latte?"
    # The evaluator saw the whole conversation, NPC lines included.
    prompt = services.llm.calls[0][1].content
    assert "BARISTA: Hi there!" in prompt and "CUSTOMER: I want hot latte." in prompt


def test_transcript_fix_is_used_for_feedback(ws, services):
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json({"type": "text_utterance", "seq": 1, "text": "I want hot late."})
    _until(ws, "scene_state")
    ws.send_json({"type": "transcript_fix", "seq": 1, "corrected_text": "I want hot latte."})
    assert _until(ws, "user_transcript") == {
        "type": "user_transcript",
        "seq": 1,
        "text": "I want hot latte.",
        "words": [],
        "low_confidence_spans": [],
    }
    ws.send_json({"type": "transcript_fix", "seq": 7, "corrected_text": "x"})
    assert _until(ws, "error")["code"] == "unknown_utterance"
    ws.send_json({"type": "session_end"})
    _until(ws, "feedback_ready")
    assert "CUSTOMER: I want hot latte." in services.llm.calls[0][1].content


def test_bad_nickname_is_rejected(ws):
    ws.send_json({"type": "session_start", "nickname": "<b>hi</b>"})
    assert _until(ws, "error")["code"] == "bad_nickname"


def test_npc_speaks_through_llm_when_configured(ws, services):
    services.npc_llm = MockLLM([{"reply": "Hey! What can I get started for you?"}])
    ws.send_json({"type": "session_start"})
    reply = _until(ws, "npc_reply")
    assert reply["text"] == "Hey! What can I get started for you?"
    assert reply["source"] == "llm"
