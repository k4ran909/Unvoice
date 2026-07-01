from __future__ import annotations

import asyncio
import time
from typing import Protocol

from app.jobs.models import Job, JobMode, JobStatus
from app.util.ids import new_job_id


class JobStore(Protocol):
    async def create(self, mode: JobMode) -> Job: ...
    async def get(self, job_id: str) -> Job | None: ...
    async def update(self, job_id: str, **fields) -> Job | None: ...
    async def list_ids(self) -> list[str]: ...
    async def delete(self, job_id: str) -> None: ...


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, mode: JobMode) -> Job:
        async with self._lock:
            job = Job(
                id=new_job_id(),
                mode=mode,
                status=JobStatus.QUEUED,
                created_at=time.time(),
            )
            self._jobs[job.id] = job
            return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **fields) -> Job | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return list(self._jobs.keys())

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)


_store: JobStore = InMemoryJobStore()


def get_store() -> JobStore:
    return _store
