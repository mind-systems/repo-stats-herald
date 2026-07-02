from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    author: str
    message: str
    changed_files: tuple[str, ...]
    diffstat: str


@dataclass(frozen=True, slots=True)
class CommitContext:
    repo: str
    branch: str
    commits: tuple[Commit, ...]
