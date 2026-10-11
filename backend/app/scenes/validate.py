"""Validates scene files: JSON Schema, then cross-references the schema cannot express.

Run from backend/:  python -m app.scenes.validate [scene.yaml ...]
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.core.config import get_settings
from app.scenes.director import SLOT_NAMES, Director
from app.scenes.guard import OutputGuard
from app.scenes.loader import read_scene_file
from app.scenes.models import Scene
from app.scenes.responder import KNOWN_PLACEHOLDERS, placeholders
from app.scenes.talk import TalkGuard, TalkScene

# Actions the Director can emit. Every scene must define all of them.
DIRECTOR_ACTIONS = frozenset(
    {
        "greet", "ask_drink", "ask_size", "ask_temperature", "offer_options", "ask_change",
        "clarify", "ask_which_option", "handle_unavailable", "handle_unsupported_temperature",
        "handle_unsupported_milk", "confirm_order", "close", "acknowledge_cancel",
        "end_unfinished",
    }
)  # fmt: skip
REQUIRED_PHASES = frozenset(
    {"greeting", "ordering", "clarifying", "confirming", "completed", "cancelled"}
)


def schema_path() -> Path:
    return get_settings().scenes_dir / "schema" / "scene.schema.json"


def semantic_errors(scene: Scene) -> list[str]:
    errors: list[str] = []
    menu = scene.menu

    aliases = [a for d in menu.drinks for a in d.aliases]
    for options in (menu.sizes, menu.temperatures, menu.milks):
        aliases += [a for o in options for a in o.aliases]
    aliases += menu.extra_shots.aliases + scene.off_menu_terms
    for alias, n in Counter(aliases).items():
        if n > 1:
            errors.append(f"alias '{alias}' is used {n} times")

    temperature_ids = {t.id for t in menu.temperatures}
    for drink in menu.drinks:
        for t in drink.temperatures:
            if t not in temperature_ids:
                errors.append(f"drink '{drink.id}' uses unknown temperature '{t}'")

    for name in ("drinks", "sizes", "temperatures", "milks"):
        ids = [o.id for o in getattr(menu, name)]
        for dup, n in Counter(ids).items():
            if n > 1:
                errors.append(f"menu.{name} id '{dup}' is used {n} times")

    if menu.extra_shots.min > menu.extra_shots.max:
        errors.append("menu.extra_shots.min is greater than max")

    for slot in scene.slots.required + scene.slots.optional:
        if slot not in SLOT_NAMES:
            errors.append(f"unknown slot '{slot}'")
    if set(scene.slots.required) & set(scene.slots.optional):
        errors.append("a slot is both required and optional")

    phase_ids = {p.id for p in scene.phases}
    for missing in sorted(REQUIRED_PHASES - phase_ids):
        errors.append(f"missing phase '{missing}'")
    for phase in scene.phases:
        for nxt in phase.next:
            if nxt not in phase_ids:
                errors.append(f"phase '{phase.id}' points to unknown phase '{nxt}'")

    for missing in sorted(DIRECTOR_ACTIONS - scene.actions.keys()):
        errors.append(f"missing action '{missing}'")
    for name, action in scene.actions.items():
        if action.phase not in phase_ids:
            errors.append(f"action '{name}' uses unknown phase '{action.phase}'")
        for field in ("instruction", "fallback"):
            unknown = placeholders(getattr(action, field)) - KNOWN_PLACEHOLDERS
            if unknown:
                errors.append(f"action '{name}'.{field} has unknown placeholders {sorted(unknown)}")

    for end in scene.end_conditions:
        if end.phase and end.phase not in phase_ids:
            errors.append(f"end condition uses unknown phase '{end.phase}'")

    if not errors:
        errors += _fallback_guard_errors(scene)
    return errors


def _fallback_guard_errors(scene: Scene) -> list[str]:
    """Every fallback line must pass the output guard, or the NPC has nothing safe to say."""
    director = Director(scene)
    drink = scene.menu.drinks[0]
    director.state.slots.update(
        drink=drink.id, size=scene.menu.sizes[0].id, temperature=drink.temperatures[0]
    )
    guard = OutputGuard(scene, director.extractor)
    context = {**director.template_context(), "item": "sample item"}
    errors = []
    for name, action in scene.actions.items():
        text = action.fallback.format_map(context)
        result = guard.check(text, allowed_mentions=("sample item",))
        if not result.ok:
            errors.append(f"action '{name}' fallback fails the guard: {result.violations}")
    return errors


def validate_file(path: Path, schema: dict) -> list[str]:
    try:
        data = read_scene_file(path)
    except Exception as exc:  # malformed YAML
        return [f"cannot read: {exc}"]
    validator = Draft202012Validator(schema)
    errors = [
        f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        return errors
    try:
        scene = Scene.model_validate(data)
    except ValidationError as exc:
        return [f"model: {exc}"]
    if scene.id != path.stem:
        errors.append(f"scene id '{scene.id}' does not match file name '{path.stem}'")
    return errors + semantic_errors(scene)


def talk_errors(scene: TalkScene) -> list[str]:
    """Mission talks (scenes/talks/*.yaml): patterns compile, template lines pass the guard."""
    errors: list[str] = []
    for dup, n in Counter(s.id for s in scene.steps).items():
        if n > 1:
            errors.append(f"step id '{dup}' is used {n} times")
    if not scene.steps:
        errors.append("a talk needs at least one step")
    patterns = [(f"step '{s.id}'", p) for s in scene.steps for p in s.patterns]
    patterns += [("goodbye_patterns", p) for p in scene.goodbye_patterns]
    patterns += [("guard", p) for p in scene.guard.forbidden_patterns]
    for where, pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"{where}: bad pattern {pattern!r}: {exc}")
    if errors:
        return errors
    guard = TalkGuard(scene)
    lines = [("opening", scene.opening, False)]
    lines += [(f"step '{s.id}'.fallback", s.fallback, False) for s in scene.steps]
    lines += [
        ("closing", scene.closing, True),
        ("unfinished_closing", scene.unfinished_closing, True),
    ]
    for where, text, closing in lines:
        result = guard.check(text, closing=closing)
        if not result.ok:
            errors.append(f"{where} fails the guard: {result.violations}")
    return errors


def validate_talk_file(path: Path) -> list[str]:
    try:
        scene = TalkScene.model_validate(read_scene_file(path))
    except ValidationError as exc:
        return [f"model: {exc}"]
    except Exception as exc:  # malformed YAML
        return [f"cannot read: {exc}"]
    errors = []
    if scene.id != path.stem:
        errors.append(f"scene id '{scene.id}' does not match file name '{path.stem}'")
    return errors + talk_errors(scene)


def main(argv: list[str]) -> int:
    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    scenes_dir = get_settings().scenes_dir
    paths = [Path(p) for p in argv] or [
        *sorted(scenes_dir.glob("*.yaml")),
        *sorted((scenes_dir / "talks").glob("*.yaml")),
        *sorted((scenes_dir / "people").glob("*.yaml")),
    ]
    if not paths:
        print("no scene files found")
        return 1
    failed = 0
    for path in paths:
        is_talk = path.parent.name in ("talks", "people")
        errors = validate_talk_file(path) if is_talk else validate_file(path, schema)
        if errors:
            failed += 1
            print(f"FAIL {path}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"OK   {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
