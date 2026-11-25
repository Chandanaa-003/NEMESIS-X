from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


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

    database_url: str = "sqlite:///./nemesis.db"
    secret_key: str = "nemesis-x-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    storage_root: str = "../storage"
    upload_dir: str = "../storage/uploads"
    processed_dir: str = "../storage/processed"
    evidence_dir: str = "../storage/evidence"
    reports_dir: str = "../storage/reports"
    max_upload_size_bytes: int = 500 * 1024 * 1024
    upload_chunk_size_bytes: int = 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized CORS origin list from string or list config."""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins

    @property
    def resolved_database_url(self) -> str:
        """Resolve relative SQLite URLs against the backend directory."""
        prefix = "sqlite:///./"
        if self.database_url.startswith(prefix):
            db_relative_path = self.database_url[len(prefix) :]
            return f"sqlite:///{(BACKEND_DIR / db_relative_path).as_posix()}"
        return self.database_url

    @property
    def resolved_upload_dir(self) -> Path:
        """Resolve upload storage path relative to the backend directory."""
        raw_path = Path(self.upload_dir)
        resolved = raw_path if raw_path.is_absolute() else (BACKEND_DIR / raw_path).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
