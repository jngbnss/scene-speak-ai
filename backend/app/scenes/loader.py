from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.scenes.models import Scene


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
