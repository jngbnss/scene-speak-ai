from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    scenes_dir: Path = REPO_ROOT / "scenes"
    default_scene_id: str = "new-york-cafe"

    stt_provider: str = "mock"
    llm_provider: str = "mock"
    tts_provider: str = "mock"
    aligner_provider: str = "mock"

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    # Qwen3 thinks by default, which adds seconds per reply. None = don't send the flag.
    ollama_think: bool | None = False
    ollama_keep_alive: str = "30m"
    llm_timeout_s: float = 60.0

    whisper_model: str = "small.en"
    whisper_device: str = "cuda"  # cuda | cpu
    whisper_compute_type: str = "int8_float16"  # use int8 on cpu
    whisper_beam_size: int = 1
    # hotwords | prompt | none (EXP-ASR-001)
    whisper_context_mode: str = "prompt"

    kokoro_model_path: Path = REPO_ROOT / "models" / "kokoro" / "kokoro-v1.0.onnx"
    kokoro_voices_path: Path = REPO_ROOT / "models" / "kokoro" / "voices-v1.0.bin"
    kokoro_device: str = "cuda"  # cuda | cpu

    # Post-session alignment (wav2vec2). CPU keeps VRAM free for the live models; ~0.2 s/line.
    aligner_device: str = "cpu"  # cpu | cuda
    # None = download the pinned ONNX export into the Hugging Face cache on first use.
    aligner_model_dir: Path | None = None
    # Pauses at least this long inside a line are shown as "listen again" segments.
    long_pause_ms: int = 800

    # User recordings are kept for "listen again" and deleted after this many days.
    audio_dir: Path = REPO_ROOT / "data" / "audio"
    audio_retention_days: int = 7
    max_utterance_seconds: int = 20

    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'scenespeak.db').as_posix()}"
    # ASR words below this confidence are never used as evidence of a user mistake.
    low_confidence_threshold: float = 0.6

    # Evaluation results shown on the /report page.
    eval_results_dir: Path = REPO_ROOT / "evals" / "results"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
