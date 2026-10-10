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
        timing = ws.receive_json()
        assert timing["type"] == "turn_timing" and timing["seq"] == seq

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


def _pcm_b64(seconds: float = 1.0, rate: int = 16000) -> str:
    import base64

    return base64.b64encode(b"\x00\x01" * int(rate * seconds)).decode()


@pytest.fixture
def voice(services, tmp_path):
    from app.ai.stt.mock import MockSTT
    from app.ai.tts.mock import MockTTS
    from app.users.audio_store import AudioStore

    services.stt = MockSTT(default_text="I want hot latte.")
    services.tts = MockTTS()
    services.audio_store = AudioStore(tmp_path / "audio", retention_days=7)
    return services


def test_audio_utterance_is_transcribed_and_answered_with_audio(ws, voice):
    ws.send_json({"type": "session_start"})
    greet_audio = _until(ws, "npc_audio")
    assert greet_audio["seq"] == 1 and greet_audio["format"] == "wav"
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": _pcm_b64()}
    )
    transcript = _until(ws, "user_transcript")
    assert transcript["text"] == "I want hot latte."
    assert [w["word"] for w in transcript["words"]] == ["I", "want", "hot", "latte."]
    assert _until(ws, "npc_reply")["action"] == "ask_size"
    audio = _until(ws, "npc_audio")
    assert audio["seq"] == 2 and audio["sample_rate"] == 24000
    timing = _until(ws, "turn_timing")
    assert timing["seq"] == 1 and timing["total_ms"] >= timing["stt_ms"]
    session_dir = next((voice.audio_store.root).iterdir())
    assert [f.name for f in session_dir.iterdir()] == ["001.wav"]


def test_low_confidence_words_are_reported(ws, voice):
    from app.ai.types import Transcript, WordInfo

    class LowConfidenceSTT:
        def transcribe(self, audio, *, hotwords=None):
            assert "cold brew" in hotwords and "oat milk" in hotwords
            words = [
                WordInfo(word="oat", start=0.0, end=0.3, confidence=0.4),
                WordInfo(word="latte", start=0.3, end=0.6, confidence=0.95),
            ]
            return Transcript(
                text="oat latte",
                words=words,
                language="en",
                audio_duration_ms=600,
                latency_ms=5,
                model_id="low",
            )

    voice.stt = LowConfidenceSTT()
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": _pcm_b64()}
    )
    assert _until(ws, "user_transcript")["low_confidence_spans"] == ["oat"]


def test_tts_failure_keeps_the_conversation_going(ws, voice):
    from app.ai.types import AdapterError

    class BrokenTTS:
        def synthesize(self, text, *, voice):
            raise AdapterError("no GPU")

    voice.tts = BrokenTTS()
    ws.send_json({"type": "session_start"})
    assert _until(ws, "npc_audio_failed")["reason"] == "tts_failed"
    ws.send_json({"type": "text_utterance", "seq": 1, "text": "I want hot latte."})
    assert _until(ws, "npc_reply")["action"] == "ask_size"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"pcm16_base64": "not base64!!"}, "bad_audio"),
        ({"pcm16_base64": _pcm_b64(25)}, "bad_audio"),
        ({"pcm16_base64": "AAAA"}, "bad_audio"),  # 3 bytes: not 16-bit aligned
    ],
)
def test_bad_audio_is_rejected(ws, voice, payload, code):
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json({"type": "audio_utterance", "seq": 1, "sample_rate": 16000, **payload})
    assert _until(ws, "error")["code"] == code


def test_silence_gives_no_speech_error(ws, voice):
    from app.ai.stt.mock import MockSTT

    voice.stt = MockSTT(default_text="")
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": _pcm_b64()}
    )
    assert _until(ws, "error")["code"] == "no_speech"


def test_audio_without_stt_configured(ws):
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": _pcm_b64()}
    )
    assert _until(ws, "error")["code"] == "stt_unavailable"
