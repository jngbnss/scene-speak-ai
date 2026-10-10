import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.api.deps import Services, get_services
from app.api.messages import (
    ErrorOut,
    FeedbackPending,
    FeedbackReady,
    NpcReplyOut,
    SceneInfo,
    SceneState,
    SessionEnd,
    SessionStart,
    SessionStarted,
    TaskResult,
    TextUtterance,
    TranscriptFix,
    UserTranscript,
    client_message_adapter,
)
from app.evaluation.evaluator import Evaluator, SessionSummary, UserLine
from app.evaluation.schema import Feedback
from app.scenes.conversation import ConversationSession, TurnResult
from app.scenes.loader import SceneNotFoundError, load_scene

log = logging.getLogger(__name__)
router = APIRouter()


def evaluate_session(services: Services, session: ConversationSession) -> Feedback:
    repo = services.repo
    user_id = repo.session_user(session.id)
    past = [t for t, _ in repo.repeated_error_types(user_id, min_count=1)][:5] if user_id else []
    turn = session.director
    summary = SessionSummary(
        transcript=repo.transcript(session.id),
        user_lines=[UserLine(seq, text, words) for seq, text, words in repo.user_lines(session.id)],
        success=bool(turn.state.phase == "completed" and turn.state.user_confirmed),
        missing_required=turn.missing_required,
        past_error_types=past,
    )
    evaluator = Evaluator(session.scene, services.llm, services.settings.low_confidence_threshold)
    try:
        return evaluator.evaluate(summary)
    except Exception:  # never lose the session because feedback failed
        log.exception("evaluation crashed")
        return evaluator.default(summary)


class _Connection:
    def __init__(self, ws: WebSocket, services: Services) -> None:
        self.ws = ws
        self.services = services
        self.session: ConversationSession | None = None
        self.npc_seq = 0
        self.user_seqs: set[int] = set()

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
            reply = result.reply
            self.services.repo.add_utterance(session.id, self.npc_seq, "npc", reply.text)
            await self.send(
                NpcReplyOut(
                    seq=self.npc_seq,
                    text=reply.text,
                    action=turn.action,
                    source=reply.source,
                    latency_ms=reply.llm_latency_ms,
                )
            )
            if reply.first_violations:
                log.info("guard rejected first LLM reply: %s", reply.first_violations)
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
            await self.finish(turn.success, turn.end_reason)

    async def finish(self, success: bool, reason: str | None) -> None:
        session = self.session
        assert session is not None
        self.services.repo.finish_session(session.id, success, reason)
        await self.send(FeedbackPending(session_id=session.id))
        feedback = await asyncio.to_thread(evaluate_session, self.services, session)
        self.services.repo.save_feedback(session.id, feedback)
        await self.send(FeedbackReady(session_id=session.id, source=feedback.source))

    async def on_start(self, msg: SessionStart) -> None:
        settings = self.services.settings
        scene_id = msg.scene_id or settings.default_scene_id
        try:
            scene = load_scene(scene_id)
        except SceneNotFoundError as exc:
            await self.error("scene_not_found", str(exc))
            return
        try:
            user_id = self.services.repo.get_or_create_user(msg.nickname)
        except ValueError as exc:
            await self.error("bad_nickname", str(exc))
            return
        self.session = ConversationSession(scene, llm=self.services.npc_llm)
        self.services.repo.create_session(self.session.id, user_id, scene.id)
        self.npc_seq = 0
        self.user_seqs = set()
        await self.send(
            SessionStarted(
                session_id=self.session.id,
                user_id=user_id,
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
        await self.send_turn(await asyncio.to_thread(self.session.start))

    async def on_text(self, msg: TextUtterance) -> None:
        if self.session is None:
            await self.error("no_session", "Send session_start first.")
            return
        if self.session.ended:
            await self.error("session_ended", "This scene has ended. Start a new session.")
            return
        self.user_seqs.add(msg.seq)
        self.services.repo.add_utterance(self.session.id, msg.seq, "user", msg.text)
        await self.send(UserTranscript(seq=msg.seq, text=msg.text))
        await self.send_turn(await asyncio.to_thread(self.session.handle_text, msg.text))

    async def on_fix(self, msg: TranscriptFix) -> None:
        if self.session is None or msg.seq not in self.user_seqs:
            await self.error("unknown_utterance", "There is no such line to correct.")
            return
        if self.session.ended:
            await self.error("session_ended", "Corrections are only possible during the scene.")
            return
        self.services.repo.fix_utterance(self.session.id, msg.seq, msg.corrected_text)
        await self.send(UserTranscript(seq=msg.seq, text=msg.corrected_text))

    async def on_end(self, _: SessionEnd) -> None:
        if self.session is None:
            await self.error("no_session", "No active session.")
            return
        await self.send_turn(await asyncio.to_thread(self.session.end))


@router.websocket("/ws/session")
async def session_socket(ws: WebSocket) -> None:
    await ws.accept()
    conn = _Connection(ws, get_services())
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
                case TranscriptFix():
                    await conn.on_fix(msg)
                case SessionEnd():
                    await conn.on_end(msg)
    except WebSocketDisconnect:
        pass
