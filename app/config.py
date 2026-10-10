from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Evidelta"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./evidelta.db"
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "raw-snapshots"
    author_id_salt: str = "evidelta-author-salt-v1"
    llm_provider: str = "openrouter"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:14b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "qwen/qwen-2.5-7b-instruct"
    openrouter_api_key: str | None = None
    openrouter_site_url: str | None = "http://localhost:8501"
    openrouter_site_name: str | None = "Evidelta"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
