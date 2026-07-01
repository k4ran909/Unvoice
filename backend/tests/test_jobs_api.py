from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def _wait_for_done(client, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in {"done", "error"}:
            return last
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish: {last}")


@pytest.mark.parametrize("mode,expected", [
    ("2stem", ["vocals", "instrumental"]),
    ("4stem", ["vocals", "drums", "bass", "other"]),
])
def test_upload_poll_download_roundtrip(tmp_storage, sine_wav: Path, mode, expected):
    with _client() as client:
        with sine_wav.open("rb") as fh:
            resp = client.post(
                "/api/jobs",
                files={"file": ("3s_sine.wav", fh, "audio/wav")},
                data={"mode": mode},
            )
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["job_id"]

        final = _wait_for_done(client, job_id)
        assert final["status"] == "done"
        assert sorted(final["stems"].keys()) == sorted(expected)

        for stem in expected:
            stem_resp = client.get(f"/api/jobs/{job_id}/stems/{stem}")
            assert stem_resp.status_code == 200, stem_resp.text
            assert stem_resp.headers["content-type"] == "audio/wav"
            data = stem_resp.content
            assert len(data) > 0
            # WAV files always start with the RIFF magic header.
            assert data[:4] == b"RIFF"
            assert data[8:12] == b"WAVE"


def test_invalid_mode_rejected(tmp_storage, sine_wav: Path):
    with _client() as client:
        with sine_wav.open("rb") as fh:
            resp = client.post(
                "/api/jobs",
                files={"file": ("x.wav", fh, "audio/wav")},
                data={"mode": "bogus"},
            )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_mode"


def test_unsupported_format_rejected(tmp_storage):
    with _client() as client:
        resp = client.post(
            "/api/jobs",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"mode": "2stem"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_format"


def test_missing_job_returns_404(tmp_storage):
    with _client() as client:
        resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "job_not_found"


def test_range_request_serves_partial(tmp_storage, sine_wav: Path):
    with _client() as client:
        with sine_wav.open("rb") as fh:
            resp = client.post(
                "/api/jobs",
                files={"file": ("3s_sine.wav", fh, "audio/wav")},
                data={"mode": "2stem"},
            )
        job_id = resp.json()["job_id"]
        _wait_for_done(client, job_id)

        partial = client.get(
            f"/api/jobs/{job_id}/stems/vocals",
            headers={"Range": "bytes=0-99"},
        )
    assert partial.status_code == 206
    assert partial.headers["accept-ranges"] == "bytes"
    assert partial.headers["content-range"].startswith("bytes 0-99/")
    assert len(partial.content) == 100
