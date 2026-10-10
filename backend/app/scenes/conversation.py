"""One user's run through a scene: Director decides, Responder speaks."""

import uuid
from dataclasses import dataclass

from app.scenes.director import Director, DirectorTurn
from app.scenes.guard import OutputGuard
from app.scenes.models import Scene
from app.scenes.responder import NpcReply, Responder, TemplateResponder


@dataclass(frozen=True)
class TurnResult:
    turn: DirectorTurn
    reply: NpcReply | None


class ConversationSession:
    def __init__(self, scene: Scene, responder: Responder | None = None) -> None:
        self.id = uuid.uuid4().hex
        self.scene = scene
        self.director = Director(scene)
        guard = OutputGuard(scene, self.director.extractor)
        self.responder = responder or TemplateResponder(scene, guard)
        self.transcript: list[tuple[str, str]] = []

    @property
    def ended(self) -> bool:
        return self.director.state.phase in ("completed", "cancelled")

    def _respond(self, turn: DirectorTurn) -> TurnResult:
        reply = self.responder.reply(turn)
        self.transcript.append(("npc", reply.text))
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
