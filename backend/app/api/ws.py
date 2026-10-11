import asyncio
import base64
import binascii
import json
import logging
import re
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.ai.audio import rms_dbfs
from app.ai.types import AdapterError, AudioInput, Transcript, WordInfo
from app.api.deps import Services, get_services
from app.api.messages import (
    AudioUtterance,
    ErrorOut,
    FeedbackPending,
    FeedbackReady,
    NpcAudio,
    NpcAudioFailed,
    NpcReplyOut,
    SceneInfo,
    SceneState,
    SessionEnd,
    SessionStart,
    SessionStarted,
    TaskResult,
    TextUtterance,
    TranscriptFix,
    TurnTiming,
    UserTranscript,
    WordOut,
    client_message_adapter,
)
from app.evaluation.evaluator import Evaluator, SessionSummary, UserLine
from app.evaluation.schema import Feedback, LineSpeech
from app.evaluation.speech import analyze_line
from app.scenes.conversation import ConversationSession, TurnResult
from app.scenes.loader import SceneNotFoundError, load_any
from app.scenes.models import Scene
from app.scenes.talk import TalkScene, TalkSession

log = logging.getLogger(__name__)
router = APIRouter()

# Quieter than this is room noise, not speech; Whisper tends to answer silence with "You".
SILENCE_DBFS = -55.0
# Whisper's usual inventions on near-silence. Dropped only when it is also unsure of them.
HALLUCINATIONS = {"you", "thank you", "thanks for watching", "bye"}


def is_hallucination(transcript: Transcript) -> bool:
    text = " ".join(re.sub(r"[^a-z' ]+", " ", transcript.text.lower()).split())
    confidences = [w.confidence for w in transcript.words if w.confidence is not None]
    unsure = not confidences or sum(confidences) / len(confidences) < 0.5
    return text in HALLUCINATIONS and unsure


Session = ConversationSession | TalkSession


def scene_kind(scene: Scene | TalkScene) -> str:
    if isinstance(scene, TalkScene):
        return "chat" if scene.mode == "chat" else "talk"
    return "order"


def session_outcome(session: Session) -> tuple[bool, list[str]]:
    """(success, what the user still had to do), decided by rules, not by the LLM."""
    if isinstance(session, TalkSession):
        return session.success, session.missing_ko
    state = session.director.state
    return state.phase == "completed" and state.user_confirmed, session.director.missing_required


def evaluate_session(services: Services, session: Session) -> Feedback:
    repo = services.repo
    user_id = repo.session_user(session.id)
    past = [t for t, _ in repo.repeated_error_types(user_id, min_count=1)][:5] if user_id else []
    success, missing = session_outcome(session)
    summary = SessionSummary(
        transcript=repo.transcript(session.id),
        user_lines=[UserLine(seq, text, words) for seq, text, words in repo.user_lines(session.id)],
        success=bool(success),
        missing_required=missing,
        past_error_types=past,
    )
    evaluator = Evaluator(session.scene, services.llm, services.settings.low_confidence_threshold)
    try:
        return evaluator.evaluate(summary)
    except Exception:  # never lose the session because feedback failed
        log.exception("evaluation crashed")
        return evaluator.default(summary)


def analyze_speech(services: Services, session_id: str) -> list[LineSpeech]:
    """Pause and replay hints for every recorded line. Never blocks feedback on failure."""
    store = services.audio_store
    if store is None:
        return []
    settings = services.settings
    lines = []
    for seq, text, words in services.repo.spoken_lines(session_id):
        audio = store.load(session_id, seq)
        if audio is None or not text.strip():
            continue
        try:
            lines.append(
                analyze_line(
                    seq,
                    text,
                    words,
                    audio,
                    services.aligner,
                    low_confidence=settings.low_confidence_threshold,
                    long_pause_ms=settings.long_pause_ms,
                )
            )
        except Exception:
            log.exception("speech analysis failed for line %d", seq)
    return lines


class _Connection:
    def __init__(self, ws: WebSocket, services: Services) -> None:
        self.ws = ws
        self.services = services
        self.session: Session | None = None
        self.npc_seq = 0
        self.user_seqs: set[int] = set()

    async def send(self, msg: BaseModel) -> None:
        await self.ws.send_text(msg.model_dump_json())

    async def error(self, code: str, message: str, recoverable: bool = True) -> None:
        await self.send(ErrorOut(code=code, message=message, recoverable=recoverable))

    async def speak(self, seq: int, text: str) -> int:
        """Sends the NPC line as audio. Returns TTS time in ms. Failure never stops the scene."""
        tts = self.services.tts
        if tts is None or self.session is None:
            return 0
        voice = self.session.scene.npc.voice
        try:
            audio = await asyncio.to_thread(tts.synthesize, text, voice=voice)
        except AdapterError as exc:
            log.warning("TTS failed: %s", exc)
            await self.send(NpcAudioFailed(seq=seq, reason="tts_failed"))
            return 0
        await self.send(
            NpcAudio(
                seq=seq,
                sample_rate=audio.sample_rate,
                data_base64=base64.b64encode(audio.wav_bytes).decode("ascii"),
            )
        )
        return audio.latency_ms

    async def send_turn(
        self, result: TurnResult, *, user_seq: int = 0, stt_ms: int = 0, started: float = 0.0
    ) -> None:
        session = self.session
        assert session is not None
        turn = result.turn
        npc_ms = int((time.perf_counter() - started) * 1000) - stt_ms if started else 0
        tts_ms = 0
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
                user_turns=session.user_turns,
            )
        )
        if result.reply is not None:
            tts_ms = await self.speak(self.npc_seq, result.reply.text)
        if started:
            timing = TurnTiming(
                seq=user_seq,
                stt_ms=stt_ms,
                npc_ms=max(npc_ms, 0),
                llm_ms=result.reply.llm_latency_ms if result.reply else 0,
                tts_ms=tts_ms,
                total_ms=int((time.perf_counter() - started) * 1000),
            )
            log.info("turn timing %s", timing.model_dump_json())
            await self.send(timing)
        if turn.ended and turn.success is not None:
            await self.send(TaskResult(success=turn.success, reason=turn.end_reason))
            await self.finish(turn.success, turn.end_reason)

    async def finish(self, success: bool, reason: str | None) -> None:
        session = self.session
        assert session is not None
        self.services.repo.finish_session(session.id, success, reason)
        await self.send(FeedbackPending(session_id=session.id))
        feedback = await asyncio.to_thread(evaluate_session, self.services, session)
        feedback.speech = await asyncio.to_thread(analyze_speech, self.services, session.id)
        self.services.repo.save_feedback(session.id, feedback)
        await self.send(FeedbackReady(session_id=session.id, source=feedback.source))

    async def on_start(self, msg: SessionStart) -> None:
        settings = self.services.settings
        scene_id = msg.scene_id or settings.default_scene_id
        try:
            scene = load_any(scene_id)
        except SceneNotFoundError as exc:
            await self.error("scene_not_found", str(exc))
            return
        try:
            user_id = self.services.repo.get_or_create_user(msg.nickname)
        except ValueError as exc:
            await self.error("bad_nickname", str(exc))
            return
        if isinstance(scene, TalkScene):
            self.session = TalkSession(scene, llm=self.services.npc_llm)
            required, optional = [s.id for s in scene.steps], []
            labels = {s.id: s.description_ko for s in scene.steps}
        else:
            self.session = ConversationSession(scene, llm=self.services.npc_llm)
            required, optional, labels = scene.slots.required, scene.slots.optional, {}
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
                    required_slots=required,
                    optional_slots=optional,
                    kind=scene_kind(scene),
                    slot_labels=labels,
                    npc_role=scene.npc.role,
                ),
            )
        )
        await self.send_turn(await asyncio.to_thread(self.session.start))

    async def _check_active(self) -> bool:
        if self.session is None:
            await self.error("no_session", "Send session_start first.")
            return False
        if self.session.ended:
            await self.error("session_ended", "This scene has ended. Start a new session.")
            return False
        return True

    async def _user_turn(
        self,
        seq: int,
        text: str,
        started: float,
        words: list[WordInfo] | None = None,
        stt_ms: int = 0,
    ) -> None:
        session = self.session
        assert session is not None
        threshold = self.services.settings.low_confidence_threshold
        words = words or []
        self.user_seqs.add(seq)
        self.services.repo.add_utterance(session.id, seq, "user", text, words)
        await self.send(
            UserTranscript(
                seq=seq,
                text=text,
                words=[WordOut(**w.model_dump()) for w in words],
                low_confidence_spans=[
                    w.word for w in words if w.confidence is not None and w.confidence < threshold
                ],
            )
        )
        result = await asyncio.to_thread(session.handle_text, text)
        await self.send_turn(result, user_seq=seq, stt_ms=stt_ms, started=started)

    async def on_text(self, msg: TextUtterance) -> None:
        if await self._check_active():
            await self._user_turn(msg.seq, msg.text, time.perf_counter())

    async def on_audio(self, msg: AudioUtterance) -> None:
        started = time.perf_counter()
        if not await self._check_active():
            return
        session = self.session
        assert session is not None
        stt = self.services.stt
        if stt is None:
            await self.error("stt_unavailable", "Speech recognition is not configured.")
            return
        try:
            pcm = base64.b64decode(msg.pcm16_base64, validate=True)
        except (binascii.Error, ValueError):
            await self.error("bad_audio", "Audio must be base64-encoded 16-bit PCM.")
            return
        audio = AudioInput(pcm16=pcm, sample_rate=msg.sample_rate)
        limit = self.services.settings.max_utterance_seconds
        if len(pcm) % 2 or audio.duration_ms > limit * 1000:
            await self.error("bad_audio", f"Utterances must be 16-bit PCM and under {limit} s.")
            return
        if rms_dbfs(pcm) < SILENCE_DBFS:
            await self.error("no_speech", "No words were recognized. Please try again.")
            return
        if self.services.audio_store is not None:
            self.services.audio_store.save(session.id, msg.seq, pcm, msg.sample_rate)
        try:
            transcript = await asyncio.to_thread(
                stt.transcribe, audio, hotwords=session.scene.hotwords
            )
        except AdapterError as exc:
            log.warning("STT failed: %s", exc)
            await self.error("stt_failed", "Speech recognition failed. Please try again.")
            return
        if not transcript.text.strip() or is_hallucination(transcript):
            await self.error("no_speech", "No words were recognized. Please try again.")
            return
        await self._user_turn(
            msg.seq, transcript.text, started, transcript.words, transcript.latency_ms
        )

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
                case AudioUtterance():
                    await conn.on_audio(msg)
                case TranscriptFix():
                    await conn.on_fix(msg)
                case SessionEnd():
                    await conn.on_end(msg)
    except WebSocketDisconnect:
        pass
