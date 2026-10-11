"""Free chats with passers-by (scenes/people/*.yaml, D-032)."""

import pytest
from fastapi.testclient import TestClient

from app.ai.llm.mock import MockLLM
from app.core.config import REPO_ROOT
from app.main import app
from app.scenes.loader import list_scenes, load_any
from app.scenes.talk import TalkScene, TalkSession
from app.scenes.validate import validate_talk_file

PEOPLE = sorted((REPO_ROOT / "scenes" / "people").glob("*.yaml"))

CHAT = [
    "Hi, how are you?",
    "I'm Jun. I'm from Korea.",
    "What do you do?",
    "Cool. It was nice talking to you. Bye!",
]


def test_there_are_people_to_talk_to():
    assert len(PEOPLE) >= 10


@pytest.mark.parametrize("path", PEOPLE, ids=lambda p: p.stem)
def test_people_files_are_valid_chats(path):
    assert validate_talk_file(path) == []
    scene = load_any(path.stem)
    assert isinstance(scene, TalkScene) and scene.mode == "chat"


@pytest.mark.parametrize("path", PEOPLE, ids=lambda p: p.stem)
def test_small_talk_meets_every_goal(path):
    scene = load_any(path.stem)
    session = TalkSession(scene)
    assert session.start().reply.text == scene.opening
    for i, line in enumerate(CHAT):
        result = session.handle_text(line)
        assert result.turn.ended == (i == len(CHAT) - 1), (line, session.missing_required)
    assert session.success and result.turn.end_reason == "user_ended"
    assert result.reply.text == scene.closing


def test_chat_goes_on_after_every_goal_but_goodbye():
    session = TalkSession(load_any("frank"))
    session.start()
    for line in CHAT[:3] + ["Do you like pizza?", "Me too!"]:
        result = session.handle_text(line)
        assert result.turn.action == "respond"
    assert session.missing_required == ["bye"]


def test_leaving_early_ends_unfinished():
    session = TalkSession(load_any("lily"))
    session.start()
    result = session.handle_text("Hello! Sorry, I have to go. Bye.")
    assert result.turn.ended and result.turn.success is False
    assert result.turn.action == "end_unfinished"
    assert session.missing_required == ["introduce", "ask"]


def test_turn_limit_ends_the_chat_and_judges_goals():
    scene = load_any("sam")
    session = TalkSession(scene)
    session.start()
    lines = CHAT[:3] + ["Okay."] * scene.max_user_turns
    for line in lines[: scene.max_user_turns]:
        result = session.handle_text(line)
    assert result.turn.ended and result.turn.end_reason == "max_user_turns"
    assert result.turn.success is False  # never said goodbye


def test_chat_prompt_uses_persona_facts_and_small_talk():
    session = TalkSession(load_any("leo"), llm=MockLLM())
    session.start()
    session.handle_text("Hi!")
    system = session.messages("respond")[0].content
    assert "saxophone" in system and "small talk" in system
    assert "ask their name" in system.lower() or "where they are from" in system
    assert "never invent prices" not in system


def test_chat_goodbye_line_has_no_question():
    llm = MockLLM([{"reply": "Bye! Will you come back?"}, {"reply": "Take care, friend!"}])
    session = TalkSession(load_any("helen"))
    session.start()
    for line in CHAT[:3]:
        session.handle_text(line)
    session.llm = llm
    reply = session.handle_text("Bye!").reply
    assert reply.source == "llm_retry" and reply.text == "Take care, friend!"


def test_people_are_listed_with_scenes():
    ids = {s.id for s in list_scenes()}
    assert {p.stem for p in PEOPLE} <= ids


@pytest.mark.usefixtures("services")
def test_chat_over_websocket_reports_kind_and_goals():
    with TestClient(app) as client, client.websocket_connect("/ws/session") as ws:
        ws.send_json({"type": "session_start", "scene_id": "dave", "nickname": "jun"})
        started = ws.receive_json()
        assert started["scene"]["kind"] == "chat"
        assert started["scene"]["required_slots"] == ["greet", "introduce", "ask", "bye"]
        for seq, line in enumerate(CHAT, start=1):
            ws.send_json({"type": "text_utterance", "seq": seq, "text": line})
        while True:
            msg = ws.receive_json()
            if msg["type"] == "task_result":
                assert msg["success"] is True
                break
