from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.ingestion.models import PushCommit, PushEvent
from src.knowledge.indexer import ArtifactIndexer
from src.knowledge.source_strategy import AiFactorySourceStrategy
from src.knowledge.store import Chunk, KnowledgeStore
from src.knowledge.sync import KnowledgeSync
from src.llm.embedder import Embedder


class _FakeMirror:
    """Stub `RepoMirror`. `tree` is an `@asynccontextmanager` that
    materializes `files` (a `{relative_path: content}` dict) into a scratch
    `TemporaryDirectory` and yields its `Path`. Records every `ensure`,
    `tree`, and `default_branch` call so gate tests can assert a
    collaborator was never even consulted."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        branch: str = "main",
        require_ensure: bool = False,
    ) -> None:
        self._files = files or {}
        self._branch = branch
        self._require_ensure = require_ensure
        self._ensured = False
        self.ensure_calls: list[tuple[str, int]] = []
        self.tree_calls: list[tuple[str, int, str]] = []
        self.tree_released: list[tuple[str, int, str]] = []
        self.default_branch_calls: list[str] = []
        self.yielded_paths: list[Path] = []

    async def ensure(self, repo: str, org_id: int) -> None:
        self.ensure_calls.append((repo, org_id))
        self._ensured = True

    async def default_branch(self, repo: str) -> str:
        self.default_branch_calls.append(repo)
        if self._require_ensure and not self._ensured:
            raise AssertionError("default_branch called before ensure")
        return self._branch

    @asynccontextmanager
    async def tree(self, repo: str, org_id: int, ref: str):
        self.tree_calls.append((repo, org_id, ref))
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for relative, content in self._files.items():
                file_path = tmp_path / relative
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
            self.yielded_paths.append(tmp_path)
            try:
                yield tmp_path
            finally:
                self.tree_released.append((repo, org_id, ref))


class _FakeIndexer:
    """Records every `index`/`remove` call. `raise_on` names paths whose
    `index` call raises instead of recording — the error-path case. `log`,
    when given, is a call log shared with a `_FakeSeeder` so ordering
    between indexing and seeding can be asserted without relying on call
    order between unrelated fakes."""

    def __init__(
        self,
        raise_on: set[str] | None = None,
        log: list[str] | None = None,
    ) -> None:
        self.index_calls: list[tuple[str, str, Path]] = []
        self.remove_calls: list[tuple[str, str]] = []
        self._raise_on = raise_on or set()
        self._log = log

    async def index(self, repo: str, path: str, tree: Path) -> None:
        if path in self._raise_on:
            raise RuntimeError(f"boom: {path}")
        self.index_calls.append((repo, path, tree))
        if self._log is not None:
            self._log.append(f"index:{path}")

    async def remove(self, repo: str, path: str) -> None:
        self.remove_calls.append((repo, path))


class _FakeSeeder:
    """Records every `seed` call, optionally into a call log shared with a
    `_FakeIndexer` for ordering assertions."""

    def __init__(self, log: list[str] | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self._log = log

    async def seed(self, repo: str, org_id: int) -> None:
        self.calls.append((repo, org_id))
        if self._log is not None:
            self._log.append(f"seed:{repo}")


class _StubStrategy:
    """Records every `selects` call and always returns the configured
    fixed verdict — used where the gate's behavior, not the strategy's own
    selection rules, is under test."""

    def __init__(self, selects: bool = False) -> None:
        self.calls: list[str] = []
        self._selects = selects

    def selects(self, path: str) -> bool:
        self.calls.append(path)
        return self._selects


class _StubEmbedder(Embedder):
    """Returns a fixed-dimension zero vector per input text — enough for an
    integration case that only needs to reach the store boundary."""

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]


class _RecordingStore(KnowledgeStore):
    """In-memory `KnowledgeStore` keyed `(repo, path)`, mirroring the real
    store's replace-on-upsert contract — an upsert for an already-present
    key replaces its chunks rather than appending to them."""

    def __init__(self) -> None:
        self.data: dict[tuple[str, str], list[Chunk]] = {}

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        self.data[(repo, path)] = items

    async def delete(self, repo: str, path: str) -> None:
        self.data.pop((repo, path), None)

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        return []


def _commit(
    sha: str = "sha1",
    added: tuple[str, ...] = (),
    modified: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
    message: str = "msg",
    author: str = "dev",
) -> PushCommit:
    return PushCommit(
        sha=sha,
        message=message,
        added=tuple(added),
        modified=tuple(modified),
        removed=tuple(removed),
        author=author,
    )


def _push(
    repo: str = "repo",
    org_id: int = 1,
    branch: str = "main",
    before: str = "before-sha",
    after: str = "after-sha",
    commits: tuple[PushCommit, ...] = (),
) -> PushEvent:
    return PushEvent(
        org_id=org_id,
        org_login="org",
        repo=repo,
        branch=branch,
        before=before,
        after=after,
        commits=tuple(commits),
    )


# --- Phase 1: on_push — the canonical-ref gate ------------------------------


async def test_non_canonical_push_performs_no_indexing_removal_or_tree_open() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    strategy = _StubStrategy()
    seeder = _FakeSeeder()
    sync = KnowledgeSync(mirror, indexer, strategy, {"repo": "main"}, seeder)  # type: ignore[arg-type]
    push = _push(
        branch="feature/x",
        commits=[
            _commit(sha="s1", added=("docs/a.md",)),
            _commit(sha="s2", modified=(".ai-factory/specs/1.md",)),
            _commit(sha="s3", removed=("ROADMAP.md",)),
        ],
    )

    await sync.on_push(push)

    assert indexer.index_calls == []
    assert indexer.remove_calls == []
    assert mirror.tree_calls == []


async def test_non_canonical_push_never_consults_the_source_strategy() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    strategy = _StubStrategy()
    sync = KnowledgeSync(mirror, indexer, strategy, {"repo": "main"})  # type: ignore[arg-type]
    push = _push(branch="feature/x", commits=[_commit(removed=("ROADMAP.md",))])

    await sync.on_push(push)

    assert strategy.calls == []


async def test_non_canonical_push_does_not_invoke_the_coordination_seeder() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    strategy = _StubStrategy()
    seeder = _FakeSeeder()
    sync = KnowledgeSync(mirror, indexer, strategy, {"repo": "main"}, seeder)  # type: ignore[arg-type]
    push = _push(branch="feature/x", commits=[_commit(added=("docs/a.md",))])

    await sync.on_push(push)

    assert seeder.calls == []


async def test_non_canonical_push_still_ensures_the_mirror() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    strategy = _StubStrategy()
    sync = KnowledgeSync(mirror, indexer, strategy, {"repo": "main"})  # type: ignore[arg-type]
    push = _push(branch="feature/x", commits=[_commit(added=("docs/a.md",))])

    await sync.on_push(push)

    assert mirror.ensure_calls == [("repo", 1)]


async def test_canonical_push_indexes_changed_paths() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x", ".ai-factory/specs/1.md": "y"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {"repo": "main"})  # type: ignore[arg-type]
    push = _push(
        branch="main",
        commits=[
            _commit(sha="s1", added=("docs/a.md",)),
            _commit(sha="s2", modified=(".ai-factory/specs/1.md",)),
            _commit(sha="s3", removed=("ROADMAP.md",)),
        ],
    )

    await sync.on_push(push)

    indexed = {(repo, path) for repo, path, _ in indexer.index_calls}
    assert indexed == {("repo", "docs/a.md"), ("repo", ".ai-factory/specs/1.md")}
    assert indexer.remove_calls == [("repo", "ROADMAP.md")]


async def test_gate_uses_resolved_override_rather_than_mirror_default_branch() -> None:
    mirror = _FakeMirror(branch="main", files={"docs/a.md": "x"})

    indexer_release = _FakeIndexer()
    sync_release = KnowledgeSync(mirror, indexer_release, AiFactorySourceStrategy(), {"repo": "release"})  # type: ignore[arg-type]
    await sync_release.on_push(_push(branch="release", commits=[_commit(added=("docs/a.md",))]))
    assert indexer_release.index_calls != []

    indexer_main = _FakeIndexer()
    sync_main = KnowledgeSync(mirror, indexer_main, AiFactorySourceStrategy(), {"repo": "release"})  # type: ignore[arg-type]
    await sync_main.on_push(_push(branch="main", commits=[_commit(added=("docs/a.md",))]))
    assert indexer_main.index_calls == []


async def test_gate_uses_mirror_default_branch_when_canonical_refs_has_no_entry() -> None:
    mirror = _FakeMirror(branch="trunk", files={"docs/a.md": "x"})

    indexer_trunk = _FakeIndexer()
    sync_trunk = KnowledgeSync(mirror, indexer_trunk, AiFactorySourceStrategy(), {"other-repo": "release"})  # type: ignore[arg-type]
    await sync_trunk.on_push(_push(branch="trunk", commits=[_commit(added=("docs/a.md",))]))
    assert indexer_trunk.index_calls != []

    indexer_main = _FakeIndexer()
    sync_main = KnowledgeSync(mirror, indexer_main, AiFactorySourceStrategy(), {"other-repo": "release"})  # type: ignore[arg-type]
    await sync_main.on_push(_push(branch="main", commits=[_commit(added=("docs/a.md",))]))
    assert indexer_main.index_calls == []


# --- Phase 2: on_push — changed-path derivation -----------------------------


async def test_changed_set_is_union_of_added_modified_removed_across_commits() -> None:
    mirror = _FakeMirror(files={"added.txt": "x", "dup.txt": "x", "modified.txt": "x"})
    indexer = _FakeIndexer()
    strategy = _StubStrategy(selects=True)
    sync = KnowledgeSync(mirror, indexer, strategy, {})  # type: ignore[arg-type]
    push = _push(
        commits=[
            _commit(sha="s1", added=("added.txt", "dup.txt")),
            _commit(sha="s2", modified=("modified.txt", "dup.txt")),
            _commit(sha="s3", removed=("removed.txt",)),
        ],
    )

    await sync.on_push(push)

    indexed_paths = [path for _, path, _ in indexer.index_calls]
    assert set(indexed_paths) == {"added.txt", "dup.txt", "modified.txt"}
    assert indexed_paths.count("dup.txt") == 1
    assert indexer.remove_calls == [("repo", "removed.txt")]


async def test_tree_existence_wins_over_bucket_for_a_re_added_path() -> None:
    mirror = _FakeMirror(files={"back.txt": "x"})
    indexer = _FakeIndexer()
    strategy = _StubStrategy(selects=True)
    sync = KnowledgeSync(mirror, indexer, strategy, {})  # type: ignore[arg-type]
    push = _push(
        commits=[
            _commit(sha="s1", removed=("back.txt",)),
            _commit(sha="s2", added=("back.txt",)),
        ],
    )

    await sync.on_push(push)

    assert [(repo, path) for repo, path, _ in indexer.index_calls] == [("repo", "back.txt")]
    assert indexer.remove_calls == []


async def test_zero_commit_canonical_push_indexes_nothing_but_still_seeds() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    strategy = _StubStrategy()
    seeder = _FakeSeeder()
    sync = KnowledgeSync(mirror, indexer, strategy, {}, seeder)  # type: ignore[arg-type]
    push = _push(commits=())

    await sync.on_push(push)

    assert indexer.index_calls == []
    assert indexer.remove_calls == []
    assert seeder.calls == [("repo", 1)]


async def test_removes_a_curated_path_absent_from_the_tree() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(commits=[_commit(removed=("docs/gone.md",))])

    await sync.on_push(push)

    assert indexer.remove_calls == [("repo", "docs/gone.md")]
    assert indexer.index_calls == []


async def test_does_not_remove_a_non_curated_path_absent_from_the_tree() -> None:
    mirror = _FakeMirror()
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(commits=[_commit(removed=("src/deleted.py",))])

    await sync.on_push(push)

    assert indexer.remove_calls == []


async def test_modified_curated_path_missing_from_tree_is_treated_as_removed() -> None:
    mirror = _FakeMirror()  # docs/x.md deliberately absent
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(commits=[_commit(modified=("docs/x.md",))])

    await sync.on_push(push)

    assert indexer.remove_calls == [("repo", "docs/x.md")]
    assert indexer.index_calls == []


async def test_canonical_push_touching_only_code_paths_stores_nothing_at_the_store_boundary() -> None:
    mirror = _FakeMirror(files={"src/app.py": "print('hi')"})
    store = _RecordingStore()
    indexer = ArtifactIndexer(AiFactorySourceStrategy(), _StubEmbedder(), store)
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(commits=[_commit(added=("src/app.py",))])

    await sync.on_push(push)

    assert store.data == {}


# --- Phase 3: on_push — tree pinning and fan-out ----------------------------


async def test_tree_is_opened_at_push_after_not_at_the_ref_name() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(after="deadbeef", commits=[_commit(added=("docs/a.md",))])

    await sync.on_push(push)

    assert mirror.tree_calls == [("repo", 1, "deadbeef")]


async def test_indexer_receives_the_yielded_tree_path() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]
    push = _push(commits=[_commit(added=("docs/a.md",))])

    await sync.on_push(push)

    assert len(indexer.index_calls) == 1
    _, _, tree = indexer.index_calls[0]
    assert tree == mirror.yielded_paths[-1]


async def test_seeder_invoked_once_after_indexing_on_a_canonical_push() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x", "docs/b.md": "y"})
    log: list[str] = []
    indexer = _FakeIndexer(log=log)
    seeder = _FakeSeeder(log=log)
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {}, seeder)  # type: ignore[arg-type]
    push = _push(commits=[_commit(added=("docs/a.md", "docs/b.md"))])

    await sync.on_push(push)

    assert log[-1] == "seed:repo"
    assert log.count("seed:repo") == 1
    assert set(log[:-1]) == {"index:docs/a.md", "index:docs/b.md"}


async def test_on_push_completes_normally_when_no_seeder_was_injected() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {}, None)  # type: ignore[arg-type]
    push = _push(commits=[_commit(added=("docs/a.md",))])

    await sync.on_push(push)

    assert len(indexer.index_calls) == 1


async def test_on_push_indexer_failure_propagates_and_releases_the_mirror_tree() -> None:
    mirror = _FakeMirror(files={"docs/a.md": "x"})
    indexer = _FakeIndexer(raise_on={"docs/a.md"})
    seeder = _FakeSeeder()
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {}, seeder)  # type: ignore[arg-type]
    push = _push(commits=[_commit(added=("docs/a.md",))])

    with pytest.raises(RuntimeError):
        await sync.on_push(push)

    assert mirror.tree_released == [("repo", 1, push.after)]
    assert seeder.calls == []


# --- Phase 4: backfill — the tree walk --------------------------------------


async def test_backfill_indexes_every_non_git_file_in_the_tree() -> None:
    mirror = _FakeMirror(files={"a.txt": "1", "docs/b.md": "2", "src/c.py": "3"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert {path for _, path, _ in indexer.index_calls} == {"a.txt", "docs/b.md", "src/c.py"}


async def test_backfill_passes_repo_relative_posix_paths() -> None:
    mirror = _FakeMirror(files={"docs/nested/deep/a.md": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    paths = [path for _, path, _ in indexer.index_calls]
    assert paths == ["docs/nested/deep/a.md"]


async def test_backfill_skips_dot_git_but_indexes_dotfiles() -> None:
    mirror = _FakeMirror(
        files={
            ".git/config": "ignore-me",
            "docs/.gitignore": "x",
            "docs/.gitkeep": "y",
        }
    )
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert {path for _, path, _ in indexer.index_calls} == {"docs/.gitignore", "docs/.gitkeep"}


async def test_backfill_indexes_only_files_and_skips_directories() -> None:
    mirror = _FakeMirror(files={"a/b/c.txt": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert {path for _, path, _ in indexer.index_calls} == {"a/b/c.txt"}


async def test_backfill_on_empty_tree_indexes_nothing_without_error() -> None:
    mirror = _FakeMirror(files={})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert indexer.index_calls == []


# --- Phase 4: backfill — canonical-ref resolution and ensure ordering -------


async def test_backfill_uses_the_canonical_ref_override_and_never_consults_default_branch() -> None:
    mirror = _FakeMirror(files={"a.txt": "x"}, branch="main")
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {"repo": "release"})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert mirror.tree_calls == [("repo", 1, "release")]
    assert mirror.default_branch_calls == []


async def test_backfill_uses_the_mirror_default_branch_when_no_override_exists() -> None:
    mirror = _FakeMirror(files={"a.txt": "x"}, branch="trunk")
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert mirror.tree_calls == [("repo", 1, "trunk")]


async def test_backfill_ensures_the_mirror_before_resolving_the_canonical_ref() -> None:
    mirror = _FakeMirror(files={"a.txt": "x"}, require_ensure=True)
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)  # would raise if default_branch ran before ensure

    assert indexer.index_calls != []


# --- Phase 4: backfill — fan-out, idempotency, and failure release ---------


async def test_backfill_invokes_the_coordination_seeder_once_after_the_walk_completes() -> None:
    mirror = _FakeMirror(files={"a.txt": "x", "b.txt": "y"})
    log: list[str] = []
    indexer = _FakeIndexer(log=log)
    seeder = _FakeSeeder(log=log)
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {}, seeder)  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert log[-1] == "seed:repo"
    assert log.count("seed:repo") == 1
    assert set(log[:-1]) == {"index:a.txt", "index:b.txt"}


async def test_backfill_completes_without_a_seeder_when_none_was_injected() -> None:
    mirror = _FakeMirror(files={"a.txt": "x"})
    indexer = _FakeIndexer()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {}, None)  # type: ignore[arg-type]

    await sync.backfill("repo", 1)

    assert len(indexer.index_calls) == 1


async def test_backfill_produces_the_same_set_of_index_calls_on_a_second_run() -> None:
    mirror = _FakeMirror(files={"a.txt": "x", "docs/b.md": "y"})
    indexer_first = _FakeIndexer()
    sync_first = KnowledgeSync(mirror, indexer_first, _StubStrategy(), {})  # type: ignore[arg-type]
    await sync_first.backfill("repo", 1)

    indexer_second = _FakeIndexer()
    sync_second = KnowledgeSync(mirror, indexer_second, _StubStrategy(), {})  # type: ignore[arg-type]
    await sync_second.backfill("repo", 1)

    first_paths = [path for _, path, _ in indexer_first.index_calls]
    second_paths = [path for _, path, _ in indexer_second.index_calls]
    assert set(first_paths) == set(second_paths)
    assert len(first_paths) == len(set(first_paths))
    assert len(second_paths) == len(set(second_paths))


async def test_backfill_indexer_failure_propagates_releases_tree_and_skips_seeder() -> None:
    mirror = _FakeMirror(files={"a.txt": "x"})
    indexer = _FakeIndexer(raise_on={"a.txt"})
    seeder = _FakeSeeder()
    sync = KnowledgeSync(mirror, indexer, _StubStrategy(), {}, seeder)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        await sync.backfill("repo", 1)

    assert mirror.tree_released == [("repo", 1, "main")]
    assert seeder.calls == []


# --- Phase 5: store-level end-to-end (integration) --------------------------


async def test_two_consecutive_backfills_leave_one_copy_of_each_artifacts_chunks() -> None:
    content = "# Title\n\nSome paragraph text for chunking purposes.\n"
    mirror = _FakeMirror(files={"docs/a.md": content})
    store = _RecordingStore()
    indexer = ArtifactIndexer(AiFactorySourceStrategy(), _StubEmbedder(), store)
    sync = KnowledgeSync(mirror, indexer, AiFactorySourceStrategy(), {})  # type: ignore[arg-type]

    await sync.backfill("repo", 1)
    first_chunks = list(store.data[("repo", "docs/a.md")])

    await sync.backfill("repo", 1)
    second_chunks = store.data[("repo", "docs/a.md")]

    assert len(store.data) == 1
    assert len(second_chunks) == len(first_chunks)
