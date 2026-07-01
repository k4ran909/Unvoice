from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.config import settings
from app.jobs.models import JobStatus
from app.jobs.store import get_store
from app.storage.local import get_storage

log = logging.getLogger("unvoice.cleanup")

_SWEEP_INTERVAL = 300  # 5 minutes


async def cleanup_loop() -> None:
    while True:
        try:
            await _sweep_once()
        except Exception:  # noqa: BLE001
            log.exception("cleanup sweep failed")
        await asyncio.sleep(_SWEEP_INTERVAL)


async def _sweep_once() -> None:
    ttl = settings.job_ttl_seconds
    if ttl <= 0:
        return
    cutoff = time.time() - ttl
    store = get_store()
    storage = get_storage()

    # Walk in-memory jobs. Only sweep terminal states — an in-progress job
    # whose run time exceeds TTL must finish (or fail) before we touch its
    # files; otherwise Demucs would write into a deleted directory.
    terminal = {JobStatus.DONE, JobStatus.ERROR}
    job_ids = await store.list_ids()
    for jid in job_ids:
        job = await store.get(jid)
        if not job:
            continue
        if job.status not in terminal:
            continue
        if job.created_at and job.created_at < cutoff:
            await store.delete(jid)
            await storage.cleanup(jid)
            log.info("cleaned up job %s", jid)

    # Walk storage too — orphaned dirs (e.g. after a restart wiped the store)
    # also get swept by mtime.
    for root in (storage.uploads, storage.outputs):
        if not root.exists():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                _rmtree(entry)
                log.info("removed orphan dir %s", entry)


def _rmtree(path: Path) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)
