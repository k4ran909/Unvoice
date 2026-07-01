from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    async def save_upload(self, job_id: str, filename: str, source) -> Path:
        """Stream `source` (a Starlette UploadFile) to durable storage. Returns
        the local path that downstream code (Demucs) can read from."""

    def stem_dir(self, job_id: str) -> Path: ...

    def stem_path(self, job_id: str, stem: str) -> Path: ...

    def stem_exists(self, job_id: str, stem: str) -> bool: ...

    async def cleanup(self, job_id: str) -> None: ...
