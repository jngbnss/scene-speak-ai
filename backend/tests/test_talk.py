import pytest
from fastapi.testclient import TestClient

from app.ai.llm.mock import MockLLM
from app.core.config import REPO_ROOT
from app.main import app
from app.scenes.loader import SceneNotFoundError, list_scenes, load_any
from app.scenes.talk import TalkScene, TalkSession
from app.scenes.validate import validate_talk_file

TALKS = sorted((REPO_ROOT / "scenes" / "talks").glob("*.yaml"))

# A learner's way through each mission, one line per turn.
WALKTHROUGHS = {
    "hot-dog-stand": [
        "Hi, can I get a hot dog?",
        "Mustard and onions, please.",
        "How much is it?",
        "Here you go. Thank you!",
    ],
    "times-square-directions": [
        "Excuse me, how do I get to Central Park?",
        "How long does it take to walk?",
        "Thank you so much.",
    ],
    "hotel-check-in": [
        "Hi, I have a reservation.",
        "My name is Mina Kim.",
        "What time is breakfast?",
        "Thank you.",
    ],
    "subway-station": [
        "Which train goes to Brooklyn Bridge?",
        "How much is the fare?",
        "Can I pay with my card?",
        "Thanks!",
    ],
}


def test_every_talk_has_a_walkthrough():
    assert {p.stem for p in TALKS} == set(WALKTHROUGHS)


@pytest.mark.parametrize("path", TALKS, ids=lambda p: p.stem)
def test_talk_files_are_valid(path):
    assert validate_talk_file(path) == []


@pytest.mark.parametrize("scene_id", sorted(WALKTHROUGHS))
def test_walkthrough_completes_the_mission(scene_id):
    scene = load_any(scene_id)
    assert isinstance(scene, TalkScene)
    session = TalkSession(scene)
    assert session.start().reply.text == scene.opening
    lines = WALKTHROUGHS[scene_id]
    for i, line in enumerate(lines):
        result = session.handle_text(line)
        assert result.turn.ended == (i == len(lines) - 1), (line, session.missing_required)
    assert session.success and result.turn.success is True
    assert result.turn.action == "close" and result.reply.text == scene.closing
    assert all(v == "done" for v in result.turn.slots.values())


def test_npc_invites_the_next_missing_step():
    session = TalkSession(load_any("hot-dog-stand"))
    session.start()
    result = session.handle_text("Hi, can I get a hot dog?")
    assert result.turn.action == "respond"
    assert result.turn.missing_required == ["topping", "price", "thanks"]
    assert "Mustard" in result.reply.text  # the topping step's fallback


def test_goodbye_ends_unfinished_with_what_was_missing():
    session = TalkSession(load_any("times-square-directions"))
    session.start()
    result = session.handle_text("Never mind, bye.")
    assert result.turn.ended and result.turn.success is False
    assert result.turn.end_reason == "user_ended"
    assert "센트럴 파크 가는 길 묻기" in session.missing_ko


def test_turn_limit_ends_the_talk():
    scene = load_any("hotel-check-in")
    session = TalkSession(scene)
    session.start()
    for _ in range(scene.max_user_turns):
        result = session.handle_text("Um.")
    assert result.turn.ended and result.turn.end_reason == "max_user_turns"


def test_invented_price_is_rejected_then_retried():
    llm = MockLLM([{"reply": "That's $7, my friend."}, {"reply": "That'll be $4."}])
    session = TalkSession(load_any("hot-dog-stand"), llm=llm)
    session.start()
    reply = session.handle_text("A hot dog please. How much?").reply
    assert reply.source == "llm_retry" and reply.text == "That'll be $4."
    assert reply.first_violations == ["price not in the facts: $7"]
    # The retry prompt says what was wrong.
    assert "price not in the facts" in llm.calls[1][0].content


def test_closing_line_may_not_ask_a_question():
    llm = MockLLM([{"reply": "Bye! Anything else?"}, {"reply": "Want a soda?"}])
    session = TalkSession(load_any("hot-dog-stand"), llm=llm)
    session.start()
    reply = session.handle_text("Bye.").reply
    assert reply.source == "template_fallback"
    assert reply.text == load_any("hot-dog-stand").unfinished_closing


def test_npc_prompt_lists_only_scene_facts():
    session = TalkSession(load_any("subway-station"), llm=MockLLM())
    system = session.messages("respond")[0].content
    assert "$2.90" in system and "never invent prices" in system


@pytest.mark.parametrize("bad", ["../new-york-cafe", "NEW", "a/b", ""])
def test_scene_ids_are_checked(bad):
    with pytest.raises(SceneNotFoundError):
        load_any(bad)


def test_list_scenes_includes_cafe_and_talks():
    ids = {s.id for s in list_scenes()}
    assert {"new-york-cafe", *WALKTHROUGHS} <= ids


@pytest.mark.usefixtures("services")
def test_talk_over_websocket_until_feedback():
    with TestClient(app) as client, client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "session_start", "scene_id": "hot-dog-stand", "nickname": "jun"})
        started = ws.receive_json()
        assert started["scene"]["kind"] == "talk"
        assert started["scene"]["required_slots"] == ["order", "topping", "price", "thanks"]
        assert started["scene"]["slot_labels"]["price"] == "가격 물어보기"
        assert started["scene"]["npc_role"] == "hot dog vendor"
        seen = []
        for seq, line in enumerate(WALKTHROUGHS["hot-dog-stand"], start=1):
            ws.send_json({"type": "text_utterance", "seq": seq, "text": line})
        while True:
            msg = ws.receive_json()
            seen.append(msg["type"])
            if msg["type"] == "task_result":
                assert msg["success"] is True and msg["reason"] == "completed"
            if msg["type"] == "feedback_ready":
                break
        fb = client.get(f"/api/sessions/{msg['session_id']}/feedback").json()
    assert "task_result" in seen
    assert fb["task_success"] is True and fb["missed_information"] == []


@pytest.mark.usefixtures("services")
def test_nickname_login_returns_a_stable_id():
    with TestClient(app) as client:
        first = client.post("/api/users", json={"nickname": "mina"}).json()["user_id"]
        again = client.post("/api/users", json={"nickname": "mina"}).json()["user_id"]
        bad = client.post("/api/users", json={"nickname": "<b>"})
    assert first == again
    assert bad.status_code == 422
