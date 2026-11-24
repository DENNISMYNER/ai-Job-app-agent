"""Application configuration (environment driven, validated by Pydantic)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOBAGENT_", env_file=".env", extra="ignore"
    )

    app_name: str = "Local AI Job Application Agent"
    environment: str = "development"
    host: str = "127.0.0.1"  # never bind publicly by default
    port: int = 8000

    data_dir: Path = PROJECT_ROOT / "data"
    documents_dir: Path = PROJECT_ROOT / "documents"
    logs_dir: Path = PROJECT_ROOT / "logs"
    database_url: str | None = None  # defaults to sqlite file in data_dir

    # AI (local only - never a paid API)
    ollama_base_url: str = "http://127.0.0.1:11434"
    default_model: str = "qwen3:4b"
    embedding_model: str = "nomic-embed-text"
    ai_timeout_seconds: float = 120.0
    ai_enabled: bool = True

    # Security
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )
    secret_key: str | None = None  # Fernet key; auto-generated into data_dir if absent
    max_upload_mb: int = 10

    # Browser automation
    browser_headless: bool = False  # headed by default so the user can intervene
    browser_channel: str = "msedge"
    browser_profile_dir: Path | None = None

    # Scheduler
    scheduler_enabled: bool = True

    log_level: str = "INFO"
    retention_days: int = 0  # 0 = keep forever

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'job_agent.db').as_posix()}"

    @property
    def profile_dir(self) -> Path:
        return self.browser_profile_dir or (self.data_dir / "browser_profile")

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.documents_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
