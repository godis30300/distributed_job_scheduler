from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Distributed Asynchronous Job Scheduler"
    api_prefix: str = "/api"

    database_url: str = Field(alias="DATABASE_URL")

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    worker_poll_interval_seconds: int = Field(default=3, alias="WORKER_POLL_INTERVAL_SECONDS")
    scheduler_poll_interval_seconds: int = Field(default=10, alias="SCHEDULER_POLL_INTERVAL_SECONDS")
    worker_id: str = Field(default="worker-local", alias="WORKER_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
