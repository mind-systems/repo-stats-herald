import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


@dataclass(frozen=True)
class ReportSchedule:
    """One named report schedule: a whole-day window and the ordered
    section keys it composes."""

    name: str
    window: int
    sections: tuple[str, ...]


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
    telegram_bot_token: str
    serve_allowlist: Annotated[frozenset[int], NoDecode] = frozenset()
    github_app_id: int | None = None
    github_app_private_key_path: str | None = None
    mirror_root: str = "var/mirror"
    bootstrap_draft_root: str = "bootstrap-drafts"
    canonical_refs: Annotated[dict[str, str], NoDecode] = {}
    github_org_logins: Annotated[dict[int, str], NoDecode] = {}
    telegram_channels: Annotated[dict[int, str], NoDecode] = {}
    repo_apps: Annotated[dict[str, str], NoDecode] = {}
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "herald_username"
    postgres_password: str = "herald_password"
    postgres_db: str = "herald_database"
    project_edges: Annotated[tuple[tuple[str, str, str], ...], NoDecode] = ()
    reasoner_k: int = 8
    pivot_lang: str = "en"
    report_schedules: Annotated[tuple[ReportSchedule, ...], NoDecode] = ()
    version_increment: Literal["major", "minor", "patch"] = "patch"

    @field_validator("serve_allowlist", mode="before")
    @classmethod
    def _parse_serve_allowlist(cls, value: object) -> object:
        if isinstance(value, (set, frozenset)):
            return value
        tokens = str(value).split(",")
        return frozenset(int(token) for token in (t.strip() for t in tokens) if token)

    @field_validator(
        "canonical_refs", "github_org_logins", "telegram_channels", "repo_apps", mode="before"
    )
    @classmethod
    def _parse_json_dict(cls, value: object) -> object:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        return json.loads(value)

    @field_validator("project_edges", mode="before")
    @classmethod
    def _parse_project_edges(cls, value: object) -> object:
        if isinstance(value, (tuple, list)):
            return tuple(value)
        if not value:
            return ()

        triples = []
        for token in str(value).split(","):
            token = token.strip()
            if not token:
                continue
            if ">" not in token or ":" not in token:
                raise ValueError(
                    f"malformed PROJECT_EDGES token {token!r}: expected 'from>to:kind'"
                )
            from_repo, rest = token.split(">", 1)
            to_repo, kind = rest.split(":", 1)
            triples.append((from_repo.strip(), to_repo.strip(), kind.strip().upper()))
        return tuple(triples)

    @field_validator("report_schedules", mode="before")
    @classmethod
    def _parse_report_schedules(cls, value: object) -> object:
        if isinstance(value, (tuple, list)) and all(isinstance(item, ReportSchedule) for item in value):
            return tuple(value)
        if not value:
            return ()
        parsed = json.loads(value)
        return tuple(
            ReportSchedule(name=o["name"], window=int(o["window"]), sections=tuple(o["sections"]))
            for o in parsed
        )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
