from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, jobs
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import logging

    from app.jobs.cleanup import cleanup_loop

    log = logging.getLogger("unvoice.startup")
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    if settings.stub_runner:
        log.info("STUB_RUNNER=true — skipping Demucs pre-warm")
        health.mark_ready()
    else:
        log.info("pre-warming Demucs model %s on %s", settings.demucs_model, settings.demucs_device)
        from app.separation.separator import get_separator
        await asyncio.to_thread(get_separator().load)
        health.mark_ready()
        log.info("Demucs model loaded, /readyz is now 200")

    sweeper = asyncio.create_task(cleanup_loop(), name="unvoice.cleanup")
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


app = FastAPI(title="Unvoice", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
