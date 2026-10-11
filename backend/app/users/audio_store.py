"""User recordings on disk (never in Git). Kept for "listen again", deleted after N days."""

import re
import shutil
import time
import wave
from pathlib import Path

from app.ai.types import AudioInput

_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


class AudioStore:
    def __init__(self, root: Path, retention_days: int) -> None:
        self.root = root
        self.retention_days = retention_days

    def path(self, session_id: str, seq: int) -> Path:
        if not _SESSION_ID.match(session_id) or seq < 0:
            raise ValueError("bad session id or line number")
        return self.root / session_id / f"{seq:03d}.wav"

    def load(self, session_id: str, seq: int) -> AudioInput | None:
        """The saved recording, or None if the line was typed or the file expired."""
        try:
            path = self.path(session_id, seq)
        except ValueError:
            return None
        if not path.is_file():
            return None
        with wave.open(str(path), "rb") as w:
            return AudioInput(pcm16=w.readframes(w.getnframes()), sample_rate=w.getframerate())

    def save(self, session_id: str, seq: int, pcm16: bytes, sample_rate: int) -> Path:
        path = self.path(session_id, seq)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm16)
        return path

    def cleanup(self, now: float | None = None) -> int:
        """Deletes session folders older than the retention period. Returns how many."""
        if not self.root.is_dir():
            return 0
        cutoff = (now or time.time()) - self.retention_days * 86400
        removed = 0
        for session_dir in self.root.iterdir():
            if session_dir.is_dir() and session_dir.stat().st_mtime < cutoff:
                shutil.rmtree(session_dir, ignore_errors=True)
                removed += 1
        return removed
