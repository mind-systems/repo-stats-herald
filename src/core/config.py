from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b-instruct-q4_K_M"
    ollama_api_key: str | None = None
    ssh_host: str | None = None
    ssh_port: int = 22
    ssh_key: str | None = None
    github_webhook_secret: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
