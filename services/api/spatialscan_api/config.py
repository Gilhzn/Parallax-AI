from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage
    storage_backend: str = "local"  # local | s3
    local_storage_dir: str = "./data/storage"
    public_base_url: str = "http://localhost:8000"
    s3_bucket: str = "spatialscan"
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"

    # Job trigger
    job_trigger: str = "inline"  # inline | redis | runpod
    redis_url: str = "redis://localhost:6379/0"
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""

    # Guardrails
    max_video_seconds: int = 45
    max_upload_mb: int = 200

    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
