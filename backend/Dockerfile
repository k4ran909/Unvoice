FROM python:3.12-slim AS base

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TORCH_HOME=/models

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml

# CPU-only torch wheels — keeps the image small. Override on GPU hosts by
# rebuilding with `--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121`.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN pip install --extra-index-url $TORCH_INDEX_URL torch torchaudio \
 && pip install \
      "fastapi>=0.115" "uvicorn[standard]>=0.32" "python-multipart>=0.0.12" \
      "pydantic-settings>=2.6" "soundfile>=0.12" "numpy<2.3" "demucs>=4.0.1"

COPY backend/app /app/app

# Pre-bake the htdemucs weights into the image so cold start is instant.
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')"

EXPOSE 8000

# Healthcheck hits readyz so an orchestrator sees the container as down until
# the model is loaded.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request, sys; urllib.request.urlopen('http://127.0.0.1:8000/api/readyz', timeout=2).read()" || exit 1

# Single worker is required — in-memory job store is per-process. When you swap
# in Redis/RQ later (Storage + JobStore protocols), bump --workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
