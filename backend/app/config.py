from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_backend: str = "local"
    storage_dir: Path = Path("./storage")
    job_ttl_seconds: int = 3600

    demucs_model: str = "htdemucs"
    demucs_device: str = "cpu"
    torch_home: str | None = None

    max_upload_mb: int = 50
    # Comma-separated. Kept as str because pydantic-settings v2 JSON-decodes
    # complex fields (list[str]) BEFORE any validator runs — so a CSV env var
    # like "http://a,http://b" would raise SettingsError on boot. Split in the
    # property below instead.
    cors_origins: str = "http://localhost:5173"
    # When true, /api/jobs uses a fast file-copy stub instead of Demucs.
    # Tests flip this on; prod leaves it off.
    stub_runner: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_dir / "outputs"


settings = Settings()
