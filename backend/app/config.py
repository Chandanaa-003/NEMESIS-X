from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env`."""

    app_name: str = "NEMESIS-X"
    app_description: str = "Beyond Detection. Into Understanding."
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    debug: bool = True

    host: str = "127.0.0.1"
    port: int = 8000

    cors_origins: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    storage_root: str = "../storage"
    upload_dir: str = "../storage/uploads"
    processed_dir: str = "../storage/processed"
    evidence_dir: str = "../storage/evidence"
    reports_dir: str = "../storage/reports"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized CORS origin list from string or list config."""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
