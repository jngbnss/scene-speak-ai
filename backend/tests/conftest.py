import json
from pathlib import Path

import pytest

from app.ai.llm.mock import MockLLM
from app.api.deps import Services, set_services
from app.core.config import REPO_ROOT, Settings
from app.scenes.director import Director
from app.scenes.extractor import RuleExtractor
from app.scenes.guard import OutputGuard
from app.scenes.loader import load_scene_file
from app.scenes.models import Scene
from app.users.db import make_sessionmaker
from app.users.repository import Repository

SCENE_PATH = REPO_ROOT / "scenes" / "new-york-cafe.yaml"
DIALOGUE_CASES = REPO_ROOT / "evals" / "dialogue-cases.jsonl"


@pytest.fixture
def repo(tmp_path) -> Repository:
    return Repository(make_sessionmaker(f"sqlite:///{(tmp_path / 'test.db').as_posix()}"))


@pytest.fixture
def services(repo) -> Services:
    """Mock adapters and a throwaway database for tests that go through the API."""
    s = Services(
        settings=Settings(_env_file=None, llm_provider="mock"),
        llm=MockLLM(),
        npc_llm=None,
        repo=repo,
    )
    set_services(s)
    yield s
    set_services(None)


@pytest.fixture(scope="session")
def scene() -> Scene:
    return load_scene_file(SCENE_PATH)


@pytest.fixture
def director(scene: Scene) -> Director:
    d = Director(scene)
    d.start()
    return d


@pytest.fixture(scope="session")
def extractor(scene: Scene) -> RuleExtractor:
    return RuleExtractor(scene)


@pytest.fixture(scope="session")
def guard(scene: Scene) -> OutputGuard:
    return OutputGuard(scene)


def load_dialogue_cases(path: Path = DIALOGUE_CASES) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
