"""Long-lived services shared by all connections. Tests replace them with ``set_services``."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.ai.registry import get_llm, get_stt, get_tts
from app.ai.types import AdapterError, LLMAdapter, STTAdapter, TTSAdapter
from app.core.config import Settings, get_settings
from app.users.audio_store import AudioStore
from app.users.db import make_sessionmaker
from app.users.repository import Repository


@dataclass
class Services:
    settings: Settings
    # Used for the Learning Evaluator. In mock mode this is a MockLLM.
    llm: LLMAdapter
    # None = the NPC speaks from templates (mock mode).
    npc_llm: LLMAdapter | None
    repo: Repository
    stt: STTAdapter | None = None
    tts: TTSAdapter | None = None
    audio_store: AudioStore | None = None


_services: Services | None = None
log = logging.getLogger(__name__)


def _optional[T](kind: str, build: Callable[[], T]) -> T | None:
    """Speech is optional: a missing model file or library disables it instead of the app.

    Without TTS the NPC answers in text only; without STT the user types.
    """
    try:
        return build()
    except (AdapterError, ImportError, OSError) as exc:
        log.warning("%s disabled, continuing in text mode: %s", kind, exc)
        return None


def build_services(settings: Settings) -> Services:
    llm = get_llm(settings)
    return Services(
        settings=settings,
        llm=llm,
        npc_llm=None if settings.llm_provider == "mock" else llm,
        repo=Repository(make_sessionmaker(settings.database_url)),
        stt=_optional("STT", lambda: get_stt(settings)),
        tts=_optional("TTS", lambda: get_tts(settings)),
        audio_store=AudioStore(settings.audio_dir, settings.audio_retention_days),
    )


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services(get_settings())
    return _services


def set_services(services: Services | None) -> None:
    global _services
    _services = services
