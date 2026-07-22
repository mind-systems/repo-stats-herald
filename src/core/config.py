from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b-instruct-q4_K_M"
    embed_model: str = "nomic-embed-text"
    ollama_api_key: str | None = None
    ssh_host: str | None = None
    ssh_port: int = 22
    ssh_key: str | None = None
    github_webhook_secret: str
    serve_allowlist: Annotated[frozenset[int], NoDecode] = frozenset()
    github_app_id: int | None = None
    github_app_private_key_path: str | None = None
    mirror_root: str = "var/mirror"

    @field_validator("serve_allowlist", mode="before")
    @classmethod
    def _parse_serve_allowlist(cls, value: object) -> object:
        if isinstance(value, (set, frozenset)):
            return value
        tokens = str(value).split(",")
        return frozenset(int(token) for token in (t.strip() for t in tokens) if token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
