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


class SequenceSTT:
    """Returns the given lines in order, with low confidence on words listed in ``unsure``."""

    model_id = "seq-stt"

    def __init__(self, lines: list[str], unsure: frozenset[str] = frozenset()) -> None:
        self.lines = list(lines)
        self.unsure = unsure

    def transcribe(self, audio, *, hotwords=None):
        from app.ai.types import Transcript, WordInfo

        text = self.lines.pop(0)
        tokens = text.split()
        step = audio.duration_ms / 1000 / len(tokens)
        words = [
            WordInfo(
                word=w,
                start=round(i * step, 3),
                end=round((i + 1) * step, 3),
                confidence=0.3 if w.strip(".,?") in self.unsure else 0.95,
            )
            for i, w in enumerate(tokens)
        ]
        return Transcript(
            text=text,
            words=words,
            language="en",
            audio_duration_ms=audio.duration_ms,
            latency_ms=1,
            model_id=self.model_id,
        )


def test_spoken_session_gets_replay_segments_and_serves_recordings(ws, voice):
    lines = ["I want hot latte.", "Large, please. And can I have oat milk?", "Yes, that's all."]
    voice.stt = SequenceSTT(lines, unsure=frozenset({"oat"}))
    ws.send_json({"type": "session_start"})
    started = _until(ws, "session_started")
    _until(ws, "scene_state")
    for seq in range(1, 4):
        ws.send_json(
            {
                "type": "audio_utterance",
                "seq": seq,
                "sample_rate": 16000,
                "pcm16_base64": _pcm_b64(2),
            }
        )
        _until(ws, "scene_state")
    ready = _until(ws, "feedback_ready")
    sid = ready["session_id"]
    with TestClient(app) as client:
        fb = client.get(f"/api/sessions/{sid}/feedback").json()
        wav = client.get(f"/api/sessions/{sid}/utterances/2/audio")
        assert client.get(f"/api/sessions/{sid}/utterances/9/audio").status_code == 404
        assert client.get("/api/sessions/..%2F..%2Fx/utterances/1/audio").status_code == 404
    assert sid == started["session_id"]
    assert [s["utterance_seq"] for s in fb["speech"]] == [1, 2, 3]
    oat_line = fb["speech"][1]
    assert [w["word"] for w in oat_line["words"] if w["uncertain"]] == ["oat"]
    assert oat_line["segments"][0]["reasons"] == ["uncertain"]
    assert "oat" in oat_line["segments"][0]["text"]
    assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
    assert wav.content[:4] == b"RIFF"


def test_typed_session_has_no_speech_hints(ws, voice):
    _finish_order(ws)
    sid = _until(ws, "feedback_ready")["session_id"]
    with TestClient(app) as client:
        assert client.get(f"/api/sessions/{sid}/feedback").json()["speech"] == []


def test_near_silent_audio_is_not_sent_to_the_recognizer(ws, voice):
    import base64

    class MustNotRun:
        def transcribe(self, audio, *, hotwords=None):
            raise AssertionError("silence reached STT")

    voice.stt = MustNotRun()
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    silence = base64.b64encode(b"\x00\x00" * 16000).decode()
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": silence}
    )
    assert _until(ws, "error")["code"] == "no_speech"


def test_unsure_you_is_treated_as_no_speech(ws, voice):
    voice.stt = SequenceSTT(["You"], unsure=frozenset({"You"}))
    ws.send_json({"type": "session_start"})
    _until(ws, "scene_state")
    ws.send_json(
        {"type": "audio_utterance", "seq": 1, "sample_rate": 16000, "pcm16_base64": _pcm_b64()}
    )
    assert _until(ws, "error")["code"] == "no_speech"


def test_shadowing_with_text_and_with_audio(voice):
    voice.stt = SequenceSTT(["Can I get large latte"])
    with TestClient(app) as client:
        typed = client.post(
            "/api/shadowing",
            json={"reference": "Can I get a large latte?", "text": "Can I get a large latte"},
        ).json()
        spoken = client.post(
            "/api/shadowing",
            json={"reference": "Can I get a large latte?", "pcm16_base64": _pcm_b64(2)},
        ).json()
        assert client.post("/api/shadowing", json={"reference": "Hi"}).status_code == 422
    assert typed["missing"] == [] and typed["matched_ratio"] == 1.0
    assert spoken["heard"] == "Can I get large latte"
    assert spoken["missing"] == ["a"]
    assert spoken["speech"]["words"][0]["word"] == "Can"


def test_shadowing_audio_needs_stt():
    with TestClient(app) as client:
        res = client.post("/api/shadowing", json={"reference": "Hi", "pcm16_base64": _pcm_b64()})
    assert res.status_code == 503


def test_reports_are_listed_and_served(services, tmp_path):
    import json

    services.settings.eval_results_dir = tmp_path
    (tmp_path / "20261011-0900-suite-a.json").write_text(
        json.dumps({"kind": "suite", "label": "a", "created_at": "2026-10-11T09:00:00"})
    )
    (tmp_path / "20261011-0800-asr-b.json").write_text(json.dumps({"label": "b"}))
    (tmp_path / "broken.json").write_text("{")
    with TestClient(app) as client:
        listed = client.get("/api/reports").json()
        one = client.get("/api/reports/20261011-0800-asr-b.json").json()
        assert client.get("/api/reports/..%5Csecret.json").status_code == 404
        assert client.get("/api/reports/missing.json").status_code == 404
    assert [(r["name"], r["kind"]) for r in listed] == [
        ("20261011-0900-suite-a.json", "suite"),
        ("20261011-0800-asr-b.json", "asr"),
    ]
    assert one["label"] == "b"
