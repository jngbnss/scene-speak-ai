"""Environment fixes needed before importing the speech libraries on Windows.

- CUDA libraries are installed as pip wheels (requirements-gpu.txt) under
  ``site-packages/nvidia/*/bin``. Windows does not search there, so the directories are
  registered explicitly.
- faster-whisper imports PyAV at import time, but only uses it to decode files. We always
  pass decoded PCM, so if PyAV cannot load (e.g. Windows Smart App Control blocks its DLLs)
  an empty placeholder module is used instead.
"""

import logging
import os
import sys
import types
from functools import cache
from pathlib import Path

log = logging.getLogger(__name__)


@cache
def register_cuda_dll_dirs() -> list[str]:
    if sys.platform != "win32":
        return []
    added = []
    for base in {Path(sys.prefix), Path(sys.base_prefix)}:
        for d in (base / "Lib" / "site-packages" / "nvidia").glob("*/bin"):
            os.add_dll_directory(str(d))
            os.environ["PATH"] = f"{d}{os.pathsep}{os.environ.get('PATH', '')}"
            added.append(str(d))
    return added


@cache
def ensure_pyav_or_placeholder() -> bool:
    """True if real PyAV loaded; False if a placeholder module was installed."""
    try:
        import av  # noqa: F401

        return True
    except ImportError as exc:
        log.warning("PyAV unavailable (%s); file decoding disabled, PCM input still works", exc)
        sys.modules["av"] = types.ModuleType("av")
        return False
