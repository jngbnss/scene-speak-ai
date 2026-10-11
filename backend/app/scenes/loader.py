import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.scenes.models import Scene
from app.scenes.talk import TalkScene


class SceneNotFoundError(LookupError):
    pass


def read_scene_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scene_file(path: Path) -> Scene:
    return Scene.model_validate(read_scene_file(path))


@lru_cache
def load_scene(scene_id: str, scenes_dir: Path | None = None) -> Scene:
    directory = scenes_dir or get_settings().scenes_dir
    path = directory / f"{scene_id}.yaml"
    if not path.is_file():
        raise SceneNotFoundError(f"Scene '{scene_id}' not found in {directory}")
    return load_scene_file(path)


TALKS_DIR = "talks"
_SCENE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def load_talk_file(path: Path) -> TalkScene:
    return TalkScene.model_validate(read_scene_file(path))


@lru_cache
def load_any(scene_id: str, scenes_dir: Path | None = None) -> Scene | TalkScene:
    """A café-style ordering scene (scenes/*.yaml) or a mission talk (scenes/talks/*.yaml)."""
    if not _SCENE_ID.match(scene_id):
        raise SceneNotFoundError(f"Scene '{scene_id}' not found")
    directory = scenes_dir or get_settings().scenes_dir
    talk = directory / TALKS_DIR / f"{scene_id}.yaml"
    if talk.is_file():
        return load_talk_file(talk)
    return load_scene(scene_id, directory)


def list_scenes(scenes_dir: Path | None = None) -> list[Scene | TalkScene]:
    directory = scenes_dir or get_settings().scenes_dir
    ids = [p.stem for p in sorted(directory.glob("*.yaml"))]
    ids += [p.stem for p in sorted((directory / TALKS_DIR).glob("*.yaml"))]
    return [load_any(i, directory) for i in ids]
