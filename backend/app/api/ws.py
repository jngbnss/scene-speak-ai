import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.api.messages import (
    ErrorOut,
    NpcReplyOut,
    SceneInfo,
    SceneState,
    SessionEnd,
    SessionStart,
    SessionStarted,
    TaskResult,
    TextUtterance,
    UserTranscript,
    client_message_adapter,
)
from app.core.config import get_settings
from app.scenes.conversation import ConversationSession, TurnResult
from app.scenes.loader import SceneNotFoundError, load_scene

log = logging.getLogger(__name__)
router = APIRouter()


class _Connection:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.session: ConversationSession | None = None
        self.npc_seq = 0

    async def send(self, msg: BaseModel) -> None:
        await self.ws.send_text(msg.model_dump_json())

    async def error(self, code: str, message: str, recoverable: bool = True) -> None:
        await self.send(ErrorOut(code=code, message=message, recoverable=recoverable))

    async def send_turn(self, result: TurnResult) -> None:
        session = self.session
        assert session is not None
        turn = result.turn
        if result.reply is not None:
            self.npc_seq += 1
            await self.send(
                NpcReplyOut(
                    seq=self.npc_seq,
                    text=result.reply.text,
                    action=turn.action,
                    source=result.reply.source,
                )
            )
            if not result.reply.guard.ok:
                log.warning(
                    "guard violations on %s: %s", turn.action, result.reply.guard.violations
                )
        await self.send(
            SceneState(
                phase=turn.phase,
                slots=turn.slots,
                missing_required=turn.missing_required,
                user_turns=session.director.state.user_turns,
            )
        )
        if turn.ended and turn.success is not None:
            await self.send(TaskResult(success=turn.success, reason=turn.end_reason))

    async def on_start(self, msg: SessionStart) -> None:
        scene_id = msg.scene_id or get_settings().default_scene_id
        try:
            scene = load_scene(scene_id)
        except SceneNotFoundError as exc:
            await self.error("scene_not_found", str(exc))
            return
        self.session = ConversationSession(scene)
        self.npc_seq = 0
        await self.send(
            SessionStarted(
                session_id=self.session.id,
                scene=SceneInfo(
                    id=scene.id,
                    title=scene.title,
                    place=scene.setting.place,
                    user_role=scene.user_role,
                    goal_ko=scene.goal.description_ko,
                    required_slots=scene.slots.required,
                    optional_slots=scene.slots.optional,
                ),
            )
        )
        await self.send_turn(self.session.start())

    async def on_text(self, msg: TextUtterance) -> None:
        if self.session is None:
            await self.error("no_session", "Send session_start first.")
            return
        if self.session.ended:
            await self.error("session_ended", "This scene has ended. Start a new session.")
            return
        await self.send(UserTranscript(seq=msg.seq, text=msg.text))
        await self.send_turn(self.session.handle_text(msg.text))

    async def on_end(self, _: SessionEnd) -> None:
        if self.session is None:
            await self.error("no_session", "No active session.")
            return
        await self.send_turn(self.session.end())


@router.websocket("/ws/session")
async def session_socket(ws: WebSocket) -> None:
    await ws.accept()
    conn = _Connection(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = client_message_adapter.validate_python(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as exc:
                await conn.error("bad_message", str(exc).splitlines()[0])
                continue
            match msg:
                case SessionStart():
                    await conn.on_start(msg)
                case TextUtterance():
                    await conn.on_text(msg)
                case SessionEnd():
                    await conn.on_end(msg)
    except WebSocketDisconnect:
        pass
