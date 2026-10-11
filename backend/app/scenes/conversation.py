"""One user's run through a scene: Director decides, Responder speaks."""

import uuid
from dataclasses import dataclass

from app.ai.types import LLMAdapter
from app.scenes.director import Director, DirectorTurn
from app.scenes.guard import OutputGuard
from app.scenes.llm_assist import LLMAssist
from app.scenes.models import Scene
from app.scenes.responder import LLMResponder, NpcReply, Responder, TemplateResponder


@dataclass(frozen=True)
class TurnResult:
    turn: DirectorTurn
    reply: NpcReply | None


class ConversationSession:
    """With ``llm`` the NPC speaks through the LLM; without it, through templates."""

    def __init__(
        self, scene: Scene, llm: LLMAdapter | None = None, session_id: str | None = None
    ) -> None:
        self.id = session_id or uuid.uuid4().hex
        self.scene = scene
        self.director = Director(scene)
        guard = OutputGuard(scene, self.director.extractor)
        self.responder: Responder
        if llm is None:
            self.responder = TemplateResponder(scene, guard)
        else:
            self.responder = LLMResponder(scene, guard, llm)
            self.director.assist = LLMAssist(scene, self.director.extractor, llm)
        self.transcript: list[tuple[str, str]] = []
        self.replies: list[NpcReply] = []

    @property
    def ended(self) -> bool:
        return self.director.state.phase in ("completed", "cancelled")

    @property
    def user_turns(self) -> int:
        return self.director.state.user_turns

    def _respond(self, turn: DirectorTurn) -> TurnResult:
        reply = self.responder.reply(turn, self.transcript)
        self.transcript.append(("npc", reply.text))
        self.replies.append(reply)
        return TurnResult(turn, reply)

    def start(self) -> TurnResult:
        return self._respond(self.director.start())

    def handle_text(self, text: str) -> TurnResult:
        self.transcript.append(("user", text))
        return self._respond(self.director.handle(text))

    def end(self) -> TurnResult:
        """Ends the session at the user's request. No NPC line if it already ended."""
        if self.ended:
            return TurnResult(self.director.end_by_user(), None)
        return self._respond(self.director.end_by_user())
