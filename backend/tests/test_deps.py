from pathlib import Path

from app.api.deps import build_services
from app.core.config import Settings


def test_missing_tts_model_disables_voice_instead_of_crashing(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        tts_provider="kokoro",
        kokoro_model_path=tmp_path / "missing.onnx",
        kokoro_voices_path=tmp_path / "missing.bin",
        database_url="sqlite://",
        audio_dir=tmp_path / "audio",
    )
    services = build_services(settings)
    assert services.tts is None
    assert services.npc_llm is None  # the rest of the app still works
