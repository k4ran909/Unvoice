from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_cleanup_removes_stale_terminal_jobs(tmp_storage, sine_wav: Path, monkeypatch):
    import os

    from app.config import settings
    from app.jobs.cleanup import _sweep_once
    from app.jobs.models import JobMode, JobStatus
    from app.jobs.store import get_store
    from app.storage.local import get_storage

    monkeypatch.setattr(settings, "job_ttl_seconds", 1)

    storage = get_storage()
    store = get_store()

    # Fresh terminal job — should survive (recent)
    fresh = await store.create(JobMode.TWO_STEM)
    await store.update(fresh.id, status=JobStatus.DONE)
    storage.stem_dir(fresh.id)

    # Stale terminal job — backdate + mark done → must be swept
    stale = await store.create(JobMode.TWO_STEM)
    stale_dir = storage.stem_dir(stale.id)
    long_ago = time.time() - 10
    await store.update(stale.id, status=JobStatus.DONE, created_at=long_ago)
    os.utime(stale_dir, (long_ago, long_ago))

    # Stale RUNNING job — must NOT be swept even though it's older than TTL
    busy = await store.create(JobMode.TWO_STEM)
    busy_dir = storage.stem_dir(busy.id)
    await store.update(busy.id, status=JobStatus.RUNNING, created_at=long_ago)
    os.utime(busy_dir, (long_ago, long_ago))

    await _sweep_once()

    assert (await store.get(fresh.id)) is not None, "fresh job was wrongly swept"
    assert (await store.get(stale.id)) is None, "stale terminal job was not swept"
    assert not stale_dir.exists(), "stale terminal dir not removed"
    assert (await store.get(busy.id)) is not None, "in-progress job was wrongly swept"


def test_oversize_upload_returns_413(tmp_storage, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "max_upload_mb", 0)  # any non-zero upload is too large

    # Construct a dummy >0 byte fake-wav so size check fires.
    payload = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 1024
    with TestClient(app) as client:
        resp = client.post(
            "/api/jobs",
            files={"file": ("big.wav", payload, "audio/wav")},
            data={"mode": "2stem"},
        )
    assert resp.status_code == 413, resp.text
    assert resp.json()["error"]["code"] == "file_too_large"
