"""Application-wide settings loaded from environment / .env files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every field can be overridden via env vars prefixed ``CLICKML_``."""

    model_config = SettingsConfigDict(
        env_prefix="CLICKML_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ──
    env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "change-me-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # ── Database ──
    db_url: str = "sqlite+aiosqlite:///./clickml_pro.db"
    db_echo: bool = False

    # ── Redis / Celery ──
    redis_url: str = "redis://localhost:6379/0"
    celery_broker: str = "redis://localhost:6379/1"
    celery_backend: str = "redis://localhost:6379/2"

    # ── AWS ──
    s3_bucket: str = "clickml-pro-artifacts"

    # ── Registry ──
    registry_backend: Literal["local", "s3", "gcs"] = "local"
    registry_path: str = "./registry"

    # ── Training ──
    default_device: str = "auto"
    checkpoint_dir: str = "./checkpoints"
    wandb_project: str = "clickml-pro"

    # ── Governance ──
    gpu_quota_default: int = 100  # GPU-hours per org per month
    budget_limit_usd: float = 500.0

    # ── Airflow ──
    airflow_dags_dir: str = "~/airflow/dags"

    # ── Data ──
    data_dir: str = "./data"

    @property
    def airflow_dags_path(self) -> Path:
        return Path(self.airflow_dags_dir).expanduser()

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def checkpoint_path(self) -> Path:
        return Path(self.checkpoint_dir)

    @property
    def registry_root(self) -> Path:
        return Path(self.registry_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return (and cache) the global settings singleton."""
    return Settings()
