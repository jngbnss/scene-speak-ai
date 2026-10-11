import base64
import binascii
import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.ai.types import AdapterError, AudioInput
from app.api.deps import get_services
from app.evaluation.schema import Feedback, LineSpeech
from app.evaluation.shadowing import ShadowResult, compare
from app.evaluation.speech import analyze_line

router = APIRouter(prefix="/api")

_REPORT_NAME = re.compile(r"^[\w.\-]+\.json$")


@router.get("/sessions/{session_id}/feedback")
def session_feedback(session_id: str) -> Feedback:
    feedback = get_services().repo.get_feedback(session_id)
    if feedback is None:
        raise HTTPException(404, "Feedback is not ready or the session does not exist.")
    return feedback


@router.get("/sessions/{session_id}/utterances/{seq}/audio")
def utterance_audio(session_id: str, seq: int) -> FileResponse:
    """The user's own recording of one line, for "listen again". Gone after retention."""
    store = get_services().audio_store
    try:
        path = store.path(session_id, seq) if store else None
    except ValueError:
        path = None
    if path is None or not path.is_file():
        raise HTTPException(404, "No recording for this line (typed, or already deleted).")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.get("/users/{user_id}/review")
def user_review(user_id: int) -> dict:
    try:
        return get_services().repo.review(user_id)
    except KeyError:
        raise HTTPException(404, "No such user.") from None


class ShadowRequest(BaseModel):
    """Either a recording of the user reading ``reference`` aloud, or typed ``text``."""

    reference: str = Field(min_length=1, max_length=300)
    pcm16_base64: str | None = None
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    text: str | None = Field(default=None, max_length=300)


class ShadowResponse(ShadowResult):
    speech: LineSpeech | None = None


@router.post("/shadowing")
def shadowing(req: ShadowRequest) -> ShadowResponse:
    services = get_services()
    settings = services.settings
    if req.pcm16_base64 is None:
        if not req.text:
            raise HTTPException(422, "Send a recording or text.")
        return ShadowResponse(**compare(req.reference, req.text).model_dump())
    if services.stt is None:
        raise HTTPException(503, "Speech recognition is not configured.")
    try:
        pcm = base64.b64decode(req.pcm16_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Audio must be base64-encoded 16-bit PCM.") from None
    audio = AudioInput(pcm16=pcm, sample_rate=req.sample_rate)
    if len(pcm) % 2 or audio.duration_ms > settings.max_utterance_seconds * 1000:
        raise HTTPException(422, "Audio must be 16-bit PCM and not too long.")
    try:
        # No scene hints here: a prompt would nudge Whisper toward the reference sentence and
        # hide the very words the user left out.
        transcript = services.stt.transcribe(audio, hotwords=None)
    except AdapterError:
        raise HTTPException(502, "Speech recognition failed. Please try again.") from None
    result = compare(
        req.reference,
        transcript.text,
        transcript.words,
        low_confidence=settings.low_confidence_threshold,
    )
    speech = None
    if transcript.text.strip():
        speech = analyze_line(
            0,
            transcript.text,
            transcript.words,
            audio,
            services.aligner,
            low_confidence=settings.low_confidence_threshold,
            long_pause_ms=settings.long_pause_ms,
        )
    return ShadowResponse(**result.model_dump(), speech=speech)


@router.get("/reports")
def list_reports() -> list[dict]:
    """Evaluation result files (evals/results/*.json), newest first."""
    root = get_services().settings.eval_results_dir
    out = []
    for path in sorted(root.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "name": path.name,
                "label": data.get("label"),
                "kind": data.get("kind") or _guess_kind(path.name),
                "created_at": data.get("created_at"),
                "git_commit": data.get("git_commit"),
            }
        )
    return out


@router.get("/reports/{name}")
def get_report(name: str) -> dict:
    root = get_services().settings.eval_results_dir
    path = root / name
    if not _REPORT_NAME.match(name) or not path.is_file():
        raise HTTPException(404, "No such report.")
    return json.loads(path.read_text(encoding="utf-8"))


def _guess_kind(name: str) -> str:
    for kind in ("suite", "dialogue", "feedback", "asr"):
        if f"-{kind}-" in name:
            return kind
    return "unknown"
