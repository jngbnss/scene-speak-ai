"""Long-lived services shared by all connections. Tests replace them with ``set_services``."""

from dataclasses import dataclass

from app.ai.registry import get_llm
from app.ai.types import LLMAdapter
from app.core.config import Settings, get_settings
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


_services: Services | None = None


def build_services(settings: Settings) -> Services:
    llm = get_llm(settings)
    return Services(
        settings=settings,
        llm=llm,
        npc_llm=None if settings.llm_provider == "mock" else llm,
        repo=Repository(make_sessionmaker(settings.database_url)),
    )


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services(get_settings())
    return _services


def set_services(services: Services | None) -> None:
    global _services
    _services = services
