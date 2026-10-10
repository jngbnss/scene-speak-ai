from app.ai.llm.mock import MockLLM
from app.ai.types import AdapterError
from app.scenes.conversation import ConversationSession
from app.scenes.director import Director
from app.scenes.prompts import npc_messages
from app.scenes.responder import LLMResponder


class FailingLLM:
    model_id = "failing"

    def generate(self, *args, **kwargs):
        raise AdapterError("down")


def _turn(scene, text="I want hot latte."):
    d = Director(scene)
    d.start()
    return d.handle(text)


def test_good_reply_is_used(scene, guard):
    llm = MockLLM([{"reply": "Sure! What size would you like?"}])
    reply = LLMResponder(scene, guard, llm).reply(_turn(scene), [("user", "I want hot latte.")])
    assert (reply.text, reply.source, reply.attempts) == (
        "Sure! What size would you like?",
        "llm",
        1,
    )


def test_rejected_reply_is_retried_with_the_violation(scene, guard):
    llm = MockLLM(
        [{"reply": "Try our maple latte! What size?"}, {"reply": "What size would you like?"}]
    )
    reply = LLMResponder(scene, guard, llm).reply(_turn(scene), [])
    assert reply.source == "llm_retry"
    assert reply.first_violations == ["off-menu item: maple latte"]
    retry_messages = llm.calls[1]
    assert "maple latte" in retry_messages[-1].content


def test_two_bad_replies_fall_back_to_template(scene, guard):
    llm = MockLLM([{"reply": "How about a mocha?"}, {"reply": "As an AI I like mochas."}])
    reply = LLMResponder(scene, guard, llm).reply(_turn(scene), [])
    assert reply.source == "template_fallback"
    assert reply.text == "What size would you like? We have small, medium, or large."
    assert reply.guard.ok


def test_llm_failure_falls_back_to_template(scene, guard):
    reply = LLMResponder(scene, guard, FailingLLM()).reply(_turn(scene), [])
    assert reply.source == "template_fallback"
    assert reply.guard.ok


def test_unavailable_item_may_be_named(scene, guard):
    turn = _turn(scene, "Can I get a pumpkin spice latte?")
    llm = MockLLM([{"reply": "Sorry, we don't have pumpkin spice latte. Would a latte work?"}])
    assert LLMResponder(scene, guard, llm).reply(turn, []).source == "llm"


def test_prompt_contains_only_scene_facts_and_action(scene):
    turn = _turn(scene)
    msgs = npc_messages(scene, turn, [("npc", "Hi!"), ("user", "I want hot latte.")])
    system = msgs[0].content
    assert "Ask which size they want. Sizes: small, medium, or large." in system
    assert "cold brew (iced, milk ok)" in system
    assert "Americano (hot/iced, no milk)" in system
    assert [m.role for m in msgs] == ["system", "assistant", "user"]


def test_greeting_prompt_has_a_user_message(scene):
    turn = Director(scene).start()
    assert npc_messages(scene, turn, [])[-1].role == "user"


def test_session_with_llm_runs_end_to_end(scene):
    llm = MockLLM(
        [
            {"reply": "Hi! What can I get you?"},
            {"reply": "Sure, what size?"},
            {"reply": "A large hot latte with oat milk. Anything else?"},
            {"reply": "Great, coming right up!"},
        ]
    )
    session = ConversationSession(scene, llm=llm)
    session.start()
    session.handle_text("I want hot latte.")
    session.handle_text("Large, please. And can I have oat milk?")
    result = session.handle_text("Yes, that's all.")
    assert result.turn.success is True
    assert [r.source for r in session.replies] == ["llm"] * 4


def test_closing_line_must_not_ask_a_question(scene, guard):
    d = Director(scene)
    d.start()
    d.handle("A large hot latte with oat milk")
    turn = d.handle("Yes, that's all.")
    assert turn.action == "close" and turn.ended
    llm = MockLLM([{"reply": "Your latte. Is that everything?"}, {"reply": "Enjoy your latte!"}])
    reply = LLMResponder(scene, guard, llm).reply(turn, [])
    assert reply.source == "llm_retry"
    assert reply.first_violations == ["question after end"]
