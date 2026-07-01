from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.jobs.models import JobMode, JobStatus
from app.jobs.runner import run_separation
from app.jobs.store import get_store
from app.storage.local import FileTooLargeError, get_storage
from app.util.audio import is_allowed

log = logging.getLogger("unvoice.api")

router = APIRouter()


def _err(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


@router.post("/jobs")
async def create_job(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(...),
):
    try:
        job_mode = JobMode(mode)
    except ValueError:
        return _err("invalid_mode", f"mode must be one of {[m.value for m in JobMode]}", 400)

    if not is_allowed(file.filename, file.content_type):
        return _err("unsupported_format", f"unsupported file type: {file.content_type or file.filename}", 400)

    store = get_store()
    storage = get_storage()

    job = await store.create(job_mode)
    try:
        input_path = await storage.save_upload(job.id, file.filename or "input.bin", file)
    except FileTooLargeError as exc:
        await store.delete(job.id)
        await storage.cleanup(job.id)
        return _err("file_too_large", str(exc), 413)
    except Exception as exc:  # noqa: BLE001
        await store.update(job.id, status=JobStatus.ERROR, error=str(exc))
        return _err("upload_failed", str(exc), 500)

    background.add_task(_run_job, job.id, input_path, job_mode)
    return JSONResponse({"job_id": job.id, "status": job.status.value}, status_code=202)


async def _run_job(job_id: str, input_path: Path, mode: JobMode) -> None:
    # FastAPI's BackgroundTasks runs sync; wrap so awaits inside run_separation
    # are honored on a fresh task.
    await run_separation(job_id, input_path, mode)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await get_store().get(job_id)
    if job is None:
        return _err("job_not_found", f"no job with id {job_id}", 404)
    return job.to_public()


@router.get("/jobs/{job_id}/stems/{stem}")
async def download_stem(job_id: str, stem: str, request: Request):
    job = await get_store().get(job_id)
    if job is None:
        return _err("job_not_found", f"no job with id {job_id}", 404)
    if stem not in job.mode.stem_names():
        return _err("unknown_stem", f"stem '{stem}' is not part of this job", 404)
    storage = get_storage()
    if not storage.stem_exists(job_id, stem):
        return _err("stem_not_ready", "stem file does not yet exist", 404)

    path = storage.stem_path(job_id, stem)
    return _range_response(request, path, content_type="audio/wav", download_name=f"{stem}.wav")


_RANGE_CHUNK = 1024 * 256  # 256 KB


def _range_response(request: Request, path: Path, *, content_type: str, download_name: str) -> StreamingResponse:
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    start, end = 0, file_size - 1
    status_code = 200
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": content_type,
        "Content-Disposition": f'inline; filename="{download_name}"',
    }

    if range_header and range_header.startswith("bytes="):
        try:
            spec = range_header.removeprefix("bytes=").split("-", 1)
            if spec[0]:
                start = int(spec[0])
            if len(spec) > 1 and spec[1]:
                end = int(spec[1])
            if start > end or end >= file_size:
                raise ValueError
            status_code = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        except ValueError:
            headers["Content-Range"] = f"bytes */{file_size}"
            return StreamingResponse(iter([b""]), status_code=416, headers=headers)

    length = end - start + 1
    headers["Content-Length"] = str(length)

    async def iter_file():
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(_RANGE_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
                await asyncio.sleep(0)

    return StreamingResponse(iter_file(), status_code=status_code, headers=headers, media_type=content_type)
