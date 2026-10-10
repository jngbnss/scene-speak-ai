import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_services
from app.api.rest import router as rest_router
from app.api.ws import router as ws_router
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


def _warm_up() -> None:
    """Loads models before the first user turn (first CUDA calls take 15-30 s)."""
    services = get_services()
    if services.audio_store is not None:
        removed = services.audio_store.cleanup()
        if removed:
            log.info("deleted %d expired recording folders", removed)
    adapters = (("LLM", services.npc_llm), ("STT", services.stt), ("TTS", services.tts))
    for name, adapter in adapters:
        warm = getattr(adapter, "warm_up", None)
        if warm is None:
            continue
        try:
            warm()
            log.info("%s warmed up", name)
        except Exception as exc:  # the app still works; the first turn is just slow
            log.warning("%s warm-up failed: %s", name, exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_services()
    task = asyncio.create_task(asyncio.to_thread(_warm_up))
    yield
    task.cancel()


app = FastAPI(title="SceneSpeak AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ws_router)
app.include_router(rest_router)


@app.get("/health")
def health() -> dict[str, object]:
    s = get_services().settings
    return {
        "status": "ok",
        "providers": {
            "stt": s.stt_provider,
            "llm": s.llm_provider,
            "tts": s.tts_provider,
            "aligner": s.aligner_provider,
        },
    }
