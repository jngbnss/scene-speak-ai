"""Model-agnostic adapter contracts.

Every adapter result carries ``model_id`` and ``latency_ms`` so experiment logs can be
built from them directly. Swapping a model means adding a class that satisfies one of
these protocols and registering it in ``app.ai.registry``.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class AudioInput(BaseModel):
    pcm16: bytes = Field(repr=False)
    sample_rate: int = 16000
    # Optional label (e.g. eval file name). Lets mocks return fixed transcripts.
    source_name: str | None = None

    @property
    def duration_ms(self) -> int:
        return int(len(self.pcm16) / 2 / self.sample_rate * 1000)


class WordInfo(BaseModel):
    word: str
    start: float
    end: float
    confidence: float | None = None


class Transcript(BaseModel):
    text: str
    words: list[WordInfo]
    language: str | None
    audio_duration_ms: int
    latency_ms: int
    model_id: str


class STTAdapter(Protocol):
    def transcribe(self, audio: AudioInput, *, hotwords: list[str] | None = None) -> Transcript: ...


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResult(BaseModel):
    text: str
    parsed: dict | None = None
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model_id: str


class LLMAdapter(Protocol):
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict | None = None,
        max_tokens: int = 128,
        temperature: float = 0.6,
    ) -> LLMResult: ...


class SpeechAudio(BaseModel):
    wav_bytes: bytes = Field(repr=False)
    sample_rate: int
    latency_ms: int
    model_id: str


class TTSAdapter(Protocol):
    def synthesize(self, text: str, *, voice: str) -> SpeechAudio: ...


class AlignedWord(WordInfo):
    pause_before_ms: int


class AlignerAdapter(Protocol):
    def align(self, audio: AudioInput, text: str) -> list[AlignedWord]: ...
