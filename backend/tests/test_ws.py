import pytest
from fastapi.testclient import TestClient

from app.main import app


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
