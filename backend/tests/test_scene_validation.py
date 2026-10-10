import json

import yaml

from app.scenes.validate import main, schema_path, validate_file
from tests.conftest import SCENE_PATH


def _schema() -> dict:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def _write_variant(tmp_path, mutate) -> object:
    data = yaml.safe_load(SCENE_PATH.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "new-york-cafe.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_bundled_scene_is_valid():
    assert validate_file(SCENE_PATH, _schema()) == []


def test_cli_returns_zero_for_valid_scene():
    assert main([str(SCENE_PATH)]) == 0


def test_schema_error(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["npc"].pop("voice"))
    errors = validate_file(path, _schema())
    assert any("voice" in e for e in errors)


def test_duplicate_alias(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["menu"]["sizes"][0]["aliases"].append("latte"))
    assert any("alias 'latte'" in e for e in validate_file(path, _schema()))


def test_unknown_phase_reference(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["phases"][0]["next"].append("paying"))
    assert any("unknown phase 'paying'" in e for e in validate_file(path, _schema()))


def test_unknown_placeholder(tmp_path):
    def mutate(d):
        d["actions"]["close"]["fallback"] = "Thanks, {customer_name}!"

    assert any(
        "customer_name" in e for e in validate_file(_write_variant(tmp_path, mutate), _schema())
    )


def test_unknown_drink_temperature(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["menu"]["drinks"][0]["temperatures"].append("warm"))
    assert any("unknown temperature 'warm'" in e for e in validate_file(path, _schema()))


def test_missing_director_action(tmp_path):
    path = _write_variant(tmp_path, lambda d: d["actions"].pop("clarify"))
    assert any("missing action 'clarify'" in e for e in validate_file(path, _schema()))


def test_fallback_that_fails_guard(tmp_path):
    def mutate(d):
        d["actions"]["close"]["fallback"] = "Thanks! Try our mocha next time."

    errors = validate_file(_write_variant(tmp_path, mutate), _schema())
    assert any("fails the guard" in e for e in errors)
