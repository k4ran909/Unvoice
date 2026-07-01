from __future__ import annotations

ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus"}
ALLOWED_MIME_PREFIXES = ("audio/", "video/mp4")


def is_allowed(filename: str | None, content_type: str | None) -> bool:
    from pathlib import Path

    if filename:
        if Path(filename).suffix.lower() in ALLOWED_SUFFIXES:
            return True
    if content_type:
        ct = content_type.lower()
        if any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES):
            return True
    return False
