from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from app.config import settings
from app.jobs.models import JobMode, JobStatus
from app.jobs.store import get_store
from app.storage.local import get_storage

log = logging.getLogger("unvoice.runner")


def stem_url(job_id: str, stem: str) -> str:
    return f"/api/jobs/{job_id}/stems/{stem}"


async def _run_stub(job_id: str, input_path: Path, mode: JobMode) -> None:
    """Fast file-copy fake — used in tests so we don't load Demucs every run."""
    store = get_store()
    storage = get_storage()
    stem_dir = storage.stem_dir(job_id)
    stems = mode.stem_names()
    for i, name in enumerate(stems, start=1):
        await asyncio.to_thread(shutil.copyfile, input_path, stem_dir / f"{name}.wav")
        await asyncio.sleep(0.05)
        await store.update(job_id, progress=i / (len(stems) + 1))


async def run_separation(job_id: str, input_path: Path, mode: JobMode) -> None:
    store = get_store()
    try:
        await store.update(job_id, status=JobStatus.RUNNING, progress=0.02)

        if settings.stub_runner:
            await _run_stub(job_id, input_path, mode)
        else:
            from app.separation.separator import get_separator

            loop = asyncio.get_running_loop()

            def on_progress(p: float) -> None:
                asyncio.run_coroutine_threadsafe(
                    store.update(job_id, progress=p),
                    loop,
                )

            storage = get_storage()
            stem_dir = storage.stem_dir(job_id)
            separator = get_separator()
            await asyncio.to_thread(
                separator.separate, input_path, stem_dir, mode, on_progress
            )

        stems = mode.stem_names()
        await store.update(
            job_id,
            status=JobStatus.DONE,
            progress=1.0,
            stems={name: stem_url(job_id, name) for name in stems},
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        await store.update(job_id, status=JobStatus.ERROR, error=str(exc))
