"""WebSocket message contracts (docs/design.md 2.4). Mirrored in frontend/src/types/messages.ts."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

# ----- client -> server -------------------------------------------------------------------


class SessionStart(BaseModel):
    type: Literal["session_start"]
    scene_id: str | None = None
    nickname: str = Field(default="guest", max_length=40)


class TextUtterance(BaseModel):
    type: Literal["text_utterance"]
    seq: int
    text: str = Field(min_length=1, max_length=500)


class AudioUtterance(BaseModel):
    """One utterance cut by the browser VAD: 16-bit little-endian mono PCM, base64."""

    type: Literal["audio_utterance"]
    seq: int
    sample_rate: int = Field(ge=8000, le=48000)
    pcm16_base64: str = Field(min_length=1)


class TranscriptFix(BaseModel):
    type: Literal["transcript_fix"]
    seq: int
    corrected_text: str = Field(min_length=1, max_length=500)


class SessionEnd(BaseModel):
    type: Literal["session_end"]
    reason: Literal["user"] = "user"


ClientMessage = Annotated[
    SessionStart | TextUtterance | AudioUtterance | TranscriptFix | SessionEnd,
    Field(discriminator="type"),
]
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)

# ----- server -> client -------------------------------------------------------------------


class SceneInfo(BaseModel):
    id: str
    title: str
    place: str
    user_role: str
    goal_ko: str
    required_slots: list[str]
    optional_slots: list[str]


class SessionStarted(BaseModel):
    type: Literal["session_started"] = "session_started"
    session_id: str
    user_id: int
    scene: SceneInfo


class WordOut(BaseModel):
    word: str
    start: float
    end: float
    confidence: float | None


class UserTranscript(BaseModel):
    type: Literal["user_transcript"] = "user_transcript"
    seq: int
    text: str
    words: list[WordOut] = []
    low_confidence_spans: list[str] = []


class SceneState(BaseModel):
    type: Literal["scene_state"] = "scene_state"
    phase: str
    slots: dict[str, str | int | None]
    missing_required: list[str]
    user_turns: int


class NpcReplyOut(BaseModel):
    type: Literal["npc_reply"] = "npc_reply"
    seq: int
    text: str
    action: str
    source: str
    latency_ms: int = 0


class NpcAudio(BaseModel):
    type: Literal["npc_audio"] = "npc_audio"
    seq: int
    format: Literal["wav"] = "wav"
    sample_rate: int
    data_base64: str


class NpcAudioFailed(BaseModel):
    type: Literal["npc_audio_failed"] = "npc_audio_failed"
    seq: int
    reason: str


class TurnTiming(BaseModel):
    """Per-turn latency in ms. stt_ms is 0 for typed input."""

    type: Literal["turn_timing"] = "turn_timing"
    seq: int
    stt_ms: int
    npc_ms: int  # Director + LLM (+ retry)
    llm_ms: int
    tts_ms: int
    total_ms: int


class TaskResult(BaseModel):
    type: Literal["task_result"] = "task_result"
    success: bool
    reason: str | None


class FeedbackPending(BaseModel):
    type: Literal["feedback_pending"] = "feedback_pending"
    session_id: str


class FeedbackReady(BaseModel):
    type: Literal["feedback_ready"] = "feedback_ready"
    session_id: str
    source: str


class ErrorOut(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool = True
