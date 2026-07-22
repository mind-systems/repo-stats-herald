from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PushCommit:
    sha: str
    message: str
    added: tuple[str, ...]
    modified: tuple[str, ...]
    removed: tuple[str, ...]
    author: str


@dataclass(frozen=True, slots=True)
class PushEvent:
    org_id: int
    org_login: str
    repo: str
    branch: str
    before: str
    after: str
    commits: tuple[PushCommit, ...]


@dataclass(frozen=True, slots=True)
class InstallationEvent:
    org_id: int
    repos_added: tuple[str, ...]
    repos_removed: tuple[str, ...]
