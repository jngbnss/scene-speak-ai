"""Chooses adapter implementations from settings (``*_PROVIDER`` env vars)."""

from collections.abc import Callable

from app.ai.alignment.mock import MockAligner
from app.ai.llm.mock import MockLLM
from app.ai.stt.mock import MockSTT
from app.ai.tts.mock import MockTTS
from app.ai.types import AlignerAdapter, LLMAdapter, STTAdapter, TTSAdapter
from app.core.config import Settings

STT_PROVIDERS: dict[str, Callable[[Settings], STTAdapter]] = {"mock": lambda s: MockSTT()}
LLM_PROVIDERS: dict[str, Callable[[Settings], LLMAdapter]] = {"mock": lambda s: MockLLM()}
TTS_PROVIDERS: dict[str, Callable[[Settings], TTSAdapter]] = {"mock": lambda s: MockTTS()}
ALIGNER_PROVIDERS: dict[str, Callable[[Settings], AlignerAdapter]] = {
    "mock": lambda s: MockAligner()
}


def _pick[T](kind: str, name: str, providers: dict[str, Callable[[Settings], T]], s: Settings) -> T:
    try:
        factory = providers[name]
    except KeyError:
        raise ValueError(
            f"Unknown {kind} provider '{name}'. Available: {', '.join(sorted(providers))}"
        ) from None
    return factory(s)


def get_stt(s: Settings) -> STTAdapter:
    return _pick("STT", s.stt_provider, STT_PROVIDERS, s)


def get_llm(s: Settings) -> LLMAdapter:
    return _pick("LLM", s.llm_provider, LLM_PROVIDERS, s)


def get_tts(s: Settings) -> TTSAdapter:
    return _pick("TTS", s.tts_provider, TTS_PROVIDERS, s)


def get_aligner(s: Settings) -> AlignerAdapter:
    return _pick("aligner", s.aligner_provider, ALIGNER_PROVIDERS, s)
