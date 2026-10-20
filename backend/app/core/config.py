"""Application settings and environment configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strict typed configuration for ORIGIN backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    origin_env: Literal["development", "test", "production"] = Field(
        default="development", alias="ORIGIN_ENV"
    )
    origin_api_key: str = Field(
        default="origin-dev-scientific-key-2026", alias="ORIGIN_API_KEY"
    )
    origin_benchmark_controller_key: str = Field(
        default="origin-private-benchmark-evaluator-key-2026",
        alias="ORIGIN_BENCHMARK_CONTROLLER_KEY",
    )
    database_url: str = Field(
        default="postgresql+asyncpg://origin:origin_password@localhost:5438/origin",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6399/0",
        alias="REDIS_URL",
    )
    lab_controller_url: str = Field(
        default="http://localhost:8099",
        alias="LAB_CONTROLLER_URL",
    )
    lab_auto_seed: bool = Field(
        default=True,
        alias="LAB_AUTO_SEED",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
