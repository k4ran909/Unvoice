from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobMode(str, Enum):
    TWO_STEM = "2stem"
    FOUR_STEM = "4stem"

    def stem_names(self) -> list[str]:
        if self is JobMode.TWO_STEM:
            return ["vocals", "instrumental"]
        return ["vocals", "drums", "bass", "other"]


@dataclass
class Job:
    id: str
    mode: JobMode
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    stems: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    created_at: float = 0.0

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode.value,
            "status": self.status.value,
            "progress": round(self.progress, 3),
            "stems": dict(self.stems),
            "error": self.error,
        }
