from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///open_swe.db"

    sandbox_type: str = "docker-container"
    sandbox_image: str = ""
    sandbox_k8s_namespace: str = "default"

    max_ci_fix_rounds: int = 2

    otel_traces_enabled: bool = True
    otel_service_name: str = "open-swe"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None

    langfuse_enabled: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None


def get_settings() -> Settings:
    return Settings()
