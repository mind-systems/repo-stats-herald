import os
import subprocess
from collections.abc import AsyncGenerator, Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from src.commits.collector import GitCommitCollector
from src.core.db import create_pool
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.models import EpisodicEntry
from src.episodic.store import PgEpisodicStore
from src.knowledge.source_strategy import AiFactorySourceStrategy

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "episodic" / "schema.sql"

EMBEDDING_DIM = 768


def _dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "herald_username")
    password = os.environ.get("POSTGRES_PASSWORD", "herald_password")
    db = os.environ.get("POSTGRES_DB", "herald_database")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture
async def pg_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    pool = await create_pool(_dsn())
    schema = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)
        await conn.execute("TRUNCATE episodic_entries")
    yield pool
    await pool.close()


@pytest.fixture
def store(pg_pool: asyncpg.Pool) -> PgEpisodicStore:
    return PgEpisodicStore(pg_pool)


@pytest.fixture
def make_entry() -> Callable[..., EpisodicEntry]:
    def _make_entry(
        content: str,
        axis: int,
        value: float = 1.0,
        repo: str = "org/repo",
        org_id: int = 1,
        completed_tasks: tuple[str, ...] = ("task-1",),
        commit_shas: tuple[str, ...] = ("abc123",),
        changed_at: datetime = datetime(2024, 1, 1, tzinfo=timezone.utc),
    ) -> EpisodicEntry:
        embedding = [0.0] * EMBEDDING_DIM
        embedding[axis] = value
        return EpisodicEntry(
            repo=repo,
            org_id=org_id,
            completed_tasks=completed_tasks,
            commit_shas=commit_shas,
            content=content,
            embedding=embedding,
            changed_at=changed_at,
        )

    return _make_entry


# --- Fixtures below build a throwaway local git repo for the
# `LinkedChangeResolver.resolve` contract tests. These are independent of the
# `pg_pool`/`store` fixtures above — resolve touches git only, never
# Postgres.

_TRUNK = "trunk"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _commit(message: str, cwd: Path) -> str:
    _git(
        "-c",
        "user.name=herald-test",
        "-c",
        "user.email=herald@test.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        message,
        cwd=cwd,
    )
    return _git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


def _write_snapshot(
    repo: Path, roadmap_path: str | None, content: str, index: int, known_paths: set[str]
) -> None:
    # Remove any previously-written roadmap file this snapshot no longer
    # carries, so a `roadmap_path=None` snapshot genuinely has no roadmap
    # file in the tree (the commits-only-fallback case).
    for stale_path in known_paths - ({roadmap_path} if roadmap_path else set()):
        stale_target = repo / stale_path
        if stale_target.exists():
            stale_target.unlink()
            _git("add", stale_path, cwd=repo)
        known_paths.discard(stale_path)

    if roadmap_path is not None:
        target = repo / roadmap_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _git("add", roadmap_path, cwd=repo)
        known_paths.add(roadmap_path)
    else:
        # Keep the commit meaningfully non-empty and unrelated to the roadmap.
        marker = repo / "src_marker.txt"
        marker.write_text(f"code change {index}", encoding="utf-8")
        _git("add", "src_marker.txt", cwd=repo)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway local git repo, pinned committer identity and branch name
    (`git init -b`) so the fixture is reproducible without relying on
    ambient git config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", _TRUNK, cwd=repo)
    return repo


@pytest.fixture
def roadmap_history(git_repo: Path) -> Callable[[Iterable[tuple[str | None, str]]], tuple[Path, list[str]]]:
    """Given an ordered list of `(roadmap_relative_path, roadmap_content)`
    snapshots, writes and commits each one in turn, returning the repo path
    and the resulting commit SHAs (same order as the snapshots) so a test
    can pick any before/after pair.

    `roadmap_relative_path` is `"ROADMAP.md"`, `".ai-factory/ROADMAP.md"`,
    or `None` for a snapshot with no roadmap file at all (the
    commits-only-fallback case).
    """

    def _build(snapshots: Iterable[tuple[str | None, str]]) -> tuple[Path, list[str]]:
        known_paths: set[str] = set()
        shas = []
        for index, (roadmap_path, content) in enumerate(snapshots):
            _write_snapshot(git_repo, roadmap_path, content, index, known_paths)
            shas.append(_commit(f"snapshot {index}", cwd=git_repo))
        return git_repo, shas

    return _build


@pytest.fixture
def merge_history(git_repo: Path) -> Callable[[], tuple[Path, str, str]]:
    """Builds a base commit, two branches diverging from it with one commit
    each, and a `--no-ff` merge of both back into the base branch — returns
    `(repo_path, base_sha, merge_sha)` for the merge-safety case."""

    def _build() -> tuple[Path, str, str]:
        base_sha = _commit("base", cwd=git_repo)

        _git("checkout", "-q", "-b", "side", cwd=git_repo)
        (git_repo / "side.txt").write_text("side branch change", encoding="utf-8")
        _git("add", "side.txt", cwd=git_repo)
        _commit("side change", cwd=git_repo)

        _git("checkout", "-q", _TRUNK, cwd=git_repo)
        (git_repo / "trunk.txt").write_text("trunk branch change", encoding="utf-8")
        _git("add", "trunk.txt", cwd=git_repo)
        _commit("trunk change", cwd=git_repo)

        _git(
            "-c",
            "user.name=herald-test",
            "-c",
            "user.email=herald@test.invalid",
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "merge side into trunk",
            "side",
            cwd=git_repo,
        )
        merge_sha = _git("rev-parse", "HEAD", cwd=git_repo).stdout.strip()
        return git_repo, base_sha, merge_sha

    return _build


@pytest.fixture
def resolver() -> LinkedChangeResolver:
    return LinkedChangeResolver(GitCommitCollector(), AiFactorySourceStrategy())
