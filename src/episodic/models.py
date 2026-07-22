from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EpisodicEntry:
    repo: str
    org_id: int
    completed_tasks: tuple[str, ...]
    commit_shas: tuple[str, ...]
    content: str
    embedding: list[float]
    changed_at: datetime
    recorded_at: datetime | None = None
