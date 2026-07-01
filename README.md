# Unvoice

Vocal-removal MVP modeled on vocalremover.org. Drag-drop an audio file, pick
2-stem or 4-stem, get back per-stem playback and downloads. Local-first, but
the Dockerfile + env layout make it ready to deploy to Render/Fly/Railway with
no rearchitecting.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | FastAPI + Python 3.12 | async upload, BackgroundTasks for the job queue |
| Separator | Demucs `htdemucs` (≈80 MB) | published default; small, fast enough on CPU |
| Audio I/O | `soundfile` + `ffmpeg` (for mp3/m4a decoding) | avoids torchcodec dep |
| Frontend | Vite + React 19 + TypeScript + Tailwind v4 | minimal scaffold, fast HMR |
| Stem player | Hand-rolled Web Audio (`AudioContext` + `AudioBufferSourceNode` per stem) | sample-accurate multi-track sync; libraries (wavesurfer/howler) drift on seek or use HTMLAudio fallbacks |
| State | In-memory job store, local-disk storage | swappable via `JobStore` and `Storage` protocols |

## Project layout

```
backend/                # FastAPI + Demucs
  app/
    api/{health,jobs}.py
    jobs/{models,store,runner,cleanup}.py
    separation/separator.py     # Demucs wrapper; renames "no_vocals" → "instrumental"
    storage/{base,local}.py
    util/{audio,ids}.py
    config.py                   # pydantic-settings reads .env
    main.py                     # FastAPI app + lifespan (pre-warm + cleanup)
  tests/                        # pytest, fast (stub runner)
  Dockerfile
  pyproject.toml

frontend/               # Vite + React + Tailwind
  src/
    audio/{StemEngine,useStemEngine}.ts
    components/{Dropzone,ProgressPanel,StemPlayer,StemTrack,ErrorBanner}.tsx
    api/client.ts
    lib/{poll,format}.ts
    App.tsx
  Dockerfile
  nginx.conf

docker-compose.yml       # backend + nginx-served frontend
.env.example             # documents every env var
```

## Local setup (Windows)

Prerequisites:

- Python 3.10–3.12 (3.13+ has no torch wheels yet)
- Node 20+
- `ffmpeg` on PATH (`winget install Gyan.FFmpeg` or `choco install ffmpeg`)
- ~2 GB free RAM. Demucs peaks at 1.5–2 GB resident on a 3-min stereo song.

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .

# CPU torch (default). For CUDA, replace with:
#   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio

# First boot downloads the htdemucs weights (~80 MB) into %USERPROFILE%\.cache\torch\hub\checkpoints\
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload
```

`GET /api/readyz` will return `503 model_not_loaded` until the weights are
loaded, then flip to `200`.

### Frontend

```powershell
cd frontend
npm install
npm run dev    # http://localhost:5173 — /api is proxied to :8000
```

### Run the tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

The default suite uses a fast file-copy stub runner (set by `STUB_RUNNER=true`
in the test conftest). It does not load Demucs, so it runs in seconds. There is
no opt-in slow suite yet.

## Configuration

Every setting is an env var read by `app/config.py`. Copy `.env.example` to
`backend/.env` to override locally.

| Var | Default | Meaning |
| --- | --- | --- |
| `STORAGE_DIR` | `./storage` | Local root for `uploads/` and `outputs/` |
| `DEMUCS_MODEL` | `htdemucs` | Any model name `demucs.pretrained.get_model` accepts |
| `DEMUCS_DEVICE` | `cpu` | `cpu` or `cuda` (only if torch.cuda.is_available()) |
| `TORCH_HOME` | (unset) | Override the torch hub cache location |
| `MAX_UPLOAD_MB` | `50` | Per-upload size cap (413 returned past this) |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `JOB_TTL_SECONDS` | `3600` | Cleanup loop removes job dirs older than this |
| `STUB_RUNNER` | `false` | Tests-only flag — skips Demucs and copies the upload to each stem |

## How it works (one paragraph)

The backend exposes `POST /api/jobs` (multipart upload + mode), `GET
/api/jobs/{id}` (status + progress + stem URLs), and `GET
/api/jobs/{id}/stems/{name}` (streaming WAV with Range support). Upload is
streamed to `storage/uploads/<id>/`; a FastAPI `BackgroundTasks` enqueues the
job. `DemucsSeparator` loads `htdemucs` once at startup, then for each job runs
`apply_model` on the full waveform — its internal `tqdm` over segments is
monkey-patched so we emit honest progress ticks (one per segment, typically
4–8 ticks for a 30-second song, 30+ for a 3-minute one). For 2-stem mode we
compute `instrumental = drums + bass + other` from the same single pass — half
the compute of running Demucs twice. Stems are written as 16-bit PCM WAV via
`soundfile`. The frontend polls `/api/jobs/{id}` every 1.5 s, then loads each
stem URL through `fetch` + `AudioContext.decodeAudioData`, wires per-stem
`AudioBufferSourceNode → GainNode → master`, and schedules `node.start(ctx.currentTime + 50ms, offset)`
for every source in the same JS tick so the browser lines them up to the
sample. Solo/mute/volume act on the `GainNode.gain` with a 10 ms declick ramp.

## Known limits (MVP)

- **Single worker** — the in-memory `JobStore` lives in one process. Run
  uvicorn with `--workers 1` (the Dockerfile does this). Multi-worker requires
  swapping to Redis + RQ; the `JobStore` protocol is the seam.
- **Stems lost on restart** — the in-memory store is wiped; old files in
  `storage/outputs/` are picked up by the cleanup loop within `JOB_TTL_SECONDS`.
- **No auth, no rate limiting** — fine for local; add reverse-proxy auth + a
  rate-limiter before public exposure.
- **WAV-only stems** — a 3-min stem is ~30 MB. mp3 export is a v2 follow-up.

## Cloud deploy (when ready)

Pre-deploy sanity checklist:

```bash
# 1. Image builds (from repo root)
docker build -f backend/Dockerfile -t unvoice-backend .

# 2. Container boots and gets ready in <30s (model is baked)
docker run --rm -p 8000:8000 unvoice-backend &
until curl -sf http://localhost:8000/api/readyz; do sleep 1; done

# 3. End-to-end smoke
curl -F file=@backend/tests/fixtures/3s_sine.wav -F mode=2stem http://localhost:8000/api/jobs

# 4. Or run the whole stack:
docker compose up --build   # backend on :8000, frontend on :8080
```

Render: connect repo, point at `backend/Dockerfile`, healthcheck `/api/readyz`,
instance with **≥ 2 GB RAM** (512 MB will OOM during separation).

Fly: `fly launch --dockerfile backend/Dockerfile`, set 2 GB memory, attach a
volume at `/data` for `STORAGE_DIR`.

## Replacing the seams

| MVP | Production swap | Where |
| --- | --- | --- |
| `InMemoryJobStore` | Redis + RQ/Celery worker | `backend/app/jobs/store.py` (Protocol) + `backend/app/jobs/runner.py` |
| `LocalStorage` | S3/R2 | `backend/app/storage/base.py` (Protocol) + new `s3.py` |
| File-served stems | CDN-signed URLs | `backend/app/api/jobs.py` — change `stem_url(...)` to issue presigned URLs |

Each swap is one file. The API contract the frontend codes against does not
change.
