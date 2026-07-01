from __future__ import annotations

import contextlib
import logging
import threading
from pathlib import Path
from typing import Callable

import torch

from app.config import settings
from app.jobs.models import JobMode

log = logging.getLogger("unvoice.separator")

ProgressCallback = Callable[[float], None]

# Progress envelope: load + preprocess = 0 → 0.10, apply_model = 0.10 → 0.92,
# write WAVs = 0.92 → 1.00. Chosen so the bar moves visibly even on tiny inputs.
_APPLY_START = 0.10
_APPLY_END = 0.92


@contextlib.contextmanager
def _hooked_tqdm(on_progress: ProgressCallback | None):
    """Patch demucs.apply.tqdm.tqdm so per-segment iteration emits a progress
    callback. Demucs 4 calls tqdm.tqdm(futures, ...) to track the futures
    yielded by its ThreadPoolExecutor; we just count items as they come out."""
    if on_progress is None:
        yield
        return

    import demucs.apply

    original = demucs.apply.tqdm

    class _Stub:
        @staticmethod
        def tqdm(iterable, *args, **kwargs):
            items = list(iterable)
            total = len(items) or 1

            def gen():
                for i, item in enumerate(items, start=1):
                    yield item
                    on_progress(_APPLY_START + (_APPLY_END - _APPLY_START) * (i / total))

            return gen()

    demucs.apply.tqdm = _Stub
    try:
        yield
    finally:
        demucs.apply.tqdm = original


class DemucsSeparator:
    """Wraps demucs 4.x pretrained inference. Held as a process singleton — load
    once at startup, hold weights in RAM, reuse across jobs.

    Demucs 4.x model.sources canonical order: ['drums','bass','other','vocals'].
    For 2-stem we run separation once and sum (drums+bass+other) as instrumental
    rather than calling Demucs twice — same result, half the compute.
    """

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or settings.demucs_model
        self.device = device or settings.demucs_device
        self._model = None
        self._load_lock = threading.Lock()
        # Serializes separate() calls: demucs.apply.tqdm is patched globally
        # during a run, and PyTorch model state isn't safe under concurrent
        # apply_model from multiple threads. CPU-bound work either way, so
        # serializing doesn't cost throughput.
        self._infer_lock = threading.Lock()
        # Resolve TORCH_HOME early so the download lands where the user expects.
        if settings.torch_home:
            import os
            os.environ.setdefault("TORCH_HOME", settings.torch_home)

    def load(self) -> None:
        from demucs.pretrained import get_model

        with self._load_lock:
            if self._model is not None:
                return
            log.info("loading demucs model %s on %s", self.model_name, self.device)
            model = get_model(self.model_name)
            model.to(self.device)
            model.eval()
            self._model = model
            log.info(
                "demucs model loaded — samplerate=%d channels=%d sources=%s",
                model.samplerate, model.audio_channels, model.sources,
            )

    @property
    def samplerate(self) -> int:
        assert self._model is not None, "call load() first"
        return self._model.samplerate

    @property
    def channels(self) -> int:
        assert self._model is not None, "call load() first"
        return self._model.audio_channels

    def separate(
        self,
        input_path: Path,
        out_dir: Path,
        mode: JobMode,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Path]:
        """Run separation. Writes stems to out_dir as 16-bit PCM WAV.
        Returns {stem_name: path}.

        This is a sync method — call it from a worker thread, not the event
        loop, because torch + ffmpeg are blocking.
        """
        import soundfile as sf
        from demucs.apply import apply_model
        from demucs.audio import AudioFile

        self.load()
        assert self._model is not None
        model = self._model

        log.info("separating %s mode=%s", input_path.name, mode.value)
        if on_progress:
            on_progress(0.02)

        # Serialize the actual inference: the global tqdm patch and model
        # state aren't safe under concurrent threads. The `with` guarantees
        # release even if AudioFile.read() blows up on a malformed upload.
        with self._infer_lock:
            wav = AudioFile(str(input_path)).read(
                streams=0,
                samplerate=model.samplerate,
                channels=model.audio_channels,
            )
            ref = wav.mean(0)
            wav = (wav - ref.mean()) / ref.std().clamp_min(1e-8)

            if on_progress:
                on_progress(_APPLY_START)

            with torch.no_grad(), _hooked_tqdm(on_progress):
                sources = apply_model(
                    model,
                    wav[None],
                    device=self.device,
                    shifts=0,
                    split=True,
                    overlap=0.25,
                    progress=True,
                )[0]

            sources = sources * ref.std().clamp_min(1e-8) + ref.mean()

            if on_progress:
                on_progress(_APPLY_END)

            vocals_idx = model.sources.index("vocals")
            out_dir.mkdir(parents=True, exist_ok=True)
            written: dict[str, Path] = {}

            def write_stem(name: str, tensor: torch.Tensor) -> None:
                # demucs gives (channels, samples) float32; soundfile wants
                # (samples, channels) and clamps to [-1, 1].
                arr = tensor.detach().cpu().numpy()
                arr = arr.T.clip(-1.0, 1.0)
                target = out_dir / f"{name}.wav"
                sf.write(str(target), arr, model.samplerate, subtype="PCM_16")
                written[name] = target

            if mode is JobMode.TWO_STEM:
                vocals = sources[vocals_idx]
                instrumental = sum(
                    s for i, s in enumerate(sources) if i != vocals_idx
                )
                write_stem("vocals", vocals)
                write_stem("instrumental", instrumental)
            else:
                for idx, name in enumerate(model.sources):
                    write_stem(name, sources[idx])

            if on_progress:
                on_progress(1.0)
            log.info("separation done: %s", list(written))
            return written


_separator = DemucsSeparator()


def get_separator() -> DemucsSeparator:
    return _separator
