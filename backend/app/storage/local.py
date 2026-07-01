from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from app.config import settings

_CHUNK = 1024 * 1024  # 1 MB


class LocalStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.storage_dir).resolve()
        self.uploads = self.root / "uploads"
        self.outputs = self.root / "outputs"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, job_id: str, filename: str, source) -> Path:
        """Stream a Starlette UploadFile to disk in 1 MB chunks. Enforces
        MAX_UPLOAD_MB at write time so we don't buffer the whole file in RAM."""
        suffix = Path(filename).suffix.lower() or ".bin"
        target_dir = self.uploads / job_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"input{suffix}"

        written = 0
        max_bytes = settings.max_upload_bytes
        with target.open("wb") as fh:
            while True:
                chunk = await source.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    fh.close()
                    target.unlink(missing_ok=True)
                    raise FileTooLargeError(written, max_bytes)
                fh.write(chunk)
        return target

    def stem_dir(self, job_id: str) -> Path:
        d = self.outputs / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def stem_path(self, job_id: str, stem: str) -> Path:
        return self.stem_dir(job_id) / f"{stem}.wav"

    def stem_exists(self, job_id: str, stem: str) -> bool:
        return self.stem_path(job_id, stem).is_file()

    async def cleanup(self, job_id: str) -> None:
        await asyncio.to_thread(self._rmtree, self.uploads / job_id)
        await asyncio.to_thread(self._rmtree, self.outputs / job_id)

    @staticmethod
    def _rmtree(path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


class FileTooLargeError(Exception):
    def __init__(self, size: int, limit: int) -> None:
        super().__init__(f"upload {size} bytes exceeds {limit} byte limit")
        self.size = size
        self.limit = limit


_storage = LocalStorage()


def get_storage() -> LocalStorage:
    return _storage
