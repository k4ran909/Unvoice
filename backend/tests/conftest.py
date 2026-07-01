from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sine_wav(fixtures_dir: Path) -> Path:
    """Generate a 3 s 440 Hz stereo sine WAV once per test session."""
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    target = fixtures_dir / "3s_sine.wav"
    if not target.exists():
        sr = 44100
        t = np.arange(int(sr * 3.0)) / sr
        tone = 0.2 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
        stereo = np.stack([tone, tone], axis=1)
        sf.write(target, stereo, sr, subtype="PCM_16")
    return target


@pytest.fixture()
def tmp_storage(tmp_path: Path, monkeypatch):
    """Point STORAGE_DIR at a temp folder and reload storage + settings so each
    test is isolated."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    monkeypatch.setenv("STORAGE_DIR", str(storage_root))
    monkeypatch.setenv("STUB_RUNNER", "true")

    import importlib

    # Reimport in dependency order so the singletons rebind to the new path.
    from app import config as cfg_mod
    importlib.reload(cfg_mod)
    from app.storage import local as storage_mod
    importlib.reload(storage_mod)
    from app.jobs import store as job_store_mod
    importlib.reload(job_store_mod)
    from app.api import jobs as jobs_api_mod
    importlib.reload(jobs_api_mod)
    from app.api import health as health_mod
    importlib.reload(health_mod)
    from app import main as main_mod
    importlib.reload(main_mod)

    yield storage_root

    shutil.rmtree(storage_root, ignore_errors=True)
