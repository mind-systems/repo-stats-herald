"""Pins `CodeBootstrap`'s draft-path invariant: `_DRAFT_RELPATH` must stay
outside every source strategy's selected set, or the next canonical push
would auto-index the unreviewed draft and poison memory with no error. Also
covers the dependency surface, traversal/scoping, the single-file write
guard, idempotent re-run, and the unreviewed marker.

Fully faked and DB-free — do not import `tests/knowledge/conftest.py`
fixtures here, they open a real Postgres pool.
"""

import contextlib
import inspect
import logging
from pathlib import Path

import pytest

from src.knowledge.bootstrap import CodeBootstrap, _DRAFT_RELPATH
from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.knowledge.source_strategy import AiFactorySourceStrategy, SourceStrategy


class FakeMirror:
    """Duck-type of `RepoMirror`. `tree` yields the already-populated
    `worktree` directory passed at construction time; on exit it flips
    `tree_open` back to `False` without deleting anything — the real
    mirror's worktree reclamation is deferred to the next `ensure()`, never
    to the `tree()` context manager itself."""

    def __init__(self, worktree: Path) -> None:
        self._worktree = worktree
        self.ensure_calls: list[tuple[str, int]] = []
        self.tree_calls: list[tuple[str, int, str]] = []
        self.tree_open = False
        self.call_log: list[str] = []

    def ensure(self, repo: str, org_id: int) -> None:
        self.ensure_calls.append((repo, org_id))
        self.call_log.append("ensure")

    @contextlib.contextmanager
    def tree(self, repo: str, org_id: int, ref: str):
        self.tree_calls.append((repo, org_id, ref))
        self.call_log.append("tree")
        self.tree_open = True
        try:
            yield self._worktree
        finally:
            self.tree_open = False


class FakeDistiller:
    """Records every `distill` call, including the mirror's `tree_open`
    state read at call time (guards against `distill` moving out of the
    `with` block). Returns bodies from a fixed list, one per call, so a
    second `run` can be made to return a different body than the first;
    the last body repeats if `distill` is called more times than there are
    bodies. Never subclasses `CodeDistiller` — a plain duck-typed fake."""

    def __init__(self, mirror: FakeMirror, bodies: list[str] | None = None) -> None:
        self._mirror = mirror
        self._bodies = list(bodies) if bodies is not None else ["distilled body"]
        self._call_count = 0
        self.calls: list[tuple[str, list[str], Path]] = []
        self.tree_open_at_call: bool | None = None

    async def distill(self, repo: str, paths: list[str], tree: Path) -> str:
        self.calls.append((repo, list(paths), tree))
        self.tree_open_at_call = self._mirror.tree_open
        index = min(self._call_count, len(self._bodies) - 1)
        self._call_count += 1
        return self._bodies[index]


class RecordingStrategy(SourceStrategy):
    """Select-all strategy that records every path it was asked about —
    used where traversal/scoping is the point, not any strategy's own
    selection rules."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def selects(self, path: str) -> bool:
        self.calls.append(path)
        return True


def _build_mixed_worktree(tmp_path: Path) -> Path:
    """A fake worktree mixing source, test, vendored, generated and
    `.git`-internal files, plus an empty directory — the fixture shared
    across the traversal/scoping tasks."""
    worktree = tmp_path / "worktree"
    files = {
        "src/a/one.py": "one",
        "src/a/two.py": "two",
        "src/pkg/mod.ts": "mod",
        "tests/test_x.py": "test",
        "node_modules/left-pad/index.js": "left-pad",
        "dist/bundle.min.js": "bundle",
        "README.md": "readme",
        ".git/config": "gitconfig",
        ".git/modules/src/nested.py": "nested",
    }
    for relative, content in files.items():
        path = worktree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (worktree / "empty_dir").mkdir(parents=True, exist_ok=True)
    return worktree


def _make_bootstrap(tmp_path: Path) -> CodeBootstrap:
    """A minimal, fully-wired `CodeBootstrap` for tests that only need an
    instance to call `_frame` on, or to check construction succeeds."""
    worktree = tmp_path / "worktree"
    worktree.mkdir(exist_ok=True)
    mirror = FakeMirror(worktree)
    return CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), tmp_path / "drafts")


# --- Phase 1: the write-guard invariant (_DRAFT_RELPATH x both strategies) --


def test_draft_relpath_not_selected_by_either_strategy() -> None:
    reason = (
        f"{_DRAFT_RELPATH!r} must never be source-selected — a canonical push "
        "would auto-index the unreviewed draft into the knowledge store"
    )
    assert CodeSourceStrategy().selects(_DRAFT_RELPATH) is False, reason
    assert AiFactorySourceStrategy().selects(_DRAFT_RELPATH) is False, reason


def test_draft_relpath_with_repo_prefix_still_not_selected_by_either_strategy() -> None:
    prefixed = f"some-repo/{_DRAFT_RELPATH}"

    assert CodeSourceStrategy().selects(prefixed) is False
    assert AiFactorySourceStrategy().selects(prefixed) is False


def test_constructor_raises_runtime_error_naming_the_path_when_ai_factory_selected(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr("src.knowledge.bootstrap._DRAFT_RELPATH", ".ai-factory/specs/leak.md")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    mirror = FakeMirror(worktree)

    with pytest.raises(RuntimeError) as exc_info:
        CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), tmp_path / "drafts")

    assert ".ai-factory/specs/leak.md" in str(exc_info.value)


def test_constructor_does_not_raise_with_the_real_strategies(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)

    assert isinstance(bootstrap, CodeBootstrap)


# --- Phase 2: __init__ — dependency surface ---------------------------------


def test_constructor_exposes_exactly_mirror_distiller_strategy_draft_root() -> None:
    params = list(inspect.signature(CodeBootstrap.__init__).parameters)
    params.remove("self")

    assert params == ["mirror", "distiller", "strategy", "draft_root"]


def test_holds_no_stored_attribute_exposing_a_knowledge_store_interface(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)

    for name in vars(bootstrap):
        attr = getattr(bootstrap, name)
        assert not hasattr(attr, "query")
        assert not hasattr(attr, "upsert")
        assert not hasattr(attr, "delete")


# --- Phase 3: run — traversal and scoping -----------------------------------


async def test_run_passes_only_strategy_selected_repo_relative_posix_paths(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror)
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), tmp_path / "drafts")

    await bootstrap.run("repo", 1)

    assert len(distiller.calls) == 1
    _, paths, _ = distiller.calls[0]
    assert set(paths) == {"src/a/one.py", "src/a/two.py", "src/pkg/mod.ts"}


async def test_run_distills_with_empty_list_and_still_writes_when_nothing_is_selected(
    tmp_path,
) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "README.md").write_text("readme", encoding="utf-8")
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror)
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), draft_root)

    result = await bootstrap.run("repo", 1)

    assert distiller.calls[0][1] == []
    assert result.exists()


async def test_run_never_offers_a_git_internal_path_to_the_strategy(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    strategy = RecordingStrategy()
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), strategy, tmp_path / "drafts")

    await bootstrap.run("repo", 1)

    assert strategy.calls != []
    assert all(".git" not in path.split("/") for path in strategy.calls)


async def test_run_never_offers_a_directory_to_the_strategy(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    strategy = RecordingStrategy()
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), strategy, tmp_path / "drafts")

    await bootstrap.run("repo", 1)

    assert strategy.calls != []
    assert all((worktree / path).is_file() for path in strategy.calls)


async def test_run_ensures_the_mirror_then_opens_the_tree_at_head(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), tmp_path / "drafts")

    await bootstrap.run("repo", 7)

    assert mirror.ensure_calls == [("repo", 7)]
    assert mirror.tree_calls == [("repo", 7, "HEAD")]
    assert mirror.call_log.index("ensure") < mirror.call_log.index("tree")


async def test_run_invokes_the_distiller_while_the_worktree_is_still_open(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror)
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), tmp_path / "drafts")

    await bootstrap.run("repo", 1)

    assert distiller.tree_open_at_call is True
    _, _, tree_arg = distiller.calls[0]
    assert tree_arg == worktree


# --- Phase 4: run — where it writes -----------------------------------------


async def test_run_writes_exactly_one_file_at_the_draft_path_and_nothing_else(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), draft_root)

    await bootstrap.run("repo", 1)

    expected = draft_root / "repo" / _DRAFT_RELPATH
    written_files = {path for path in draft_root.rglob("*") if path.is_file()}
    assert written_files == {expected}


async def test_run_creates_missing_repo_ai_factory_parents_when_only_draft_root_exists(
    tmp_path,
) -> None:
    draft_root = tmp_path / "drafts"
    draft_root.mkdir()
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), draft_root)

    result = await bootstrap.run("repo", 1)

    assert result.exists()
    assert result == draft_root / "repo" / _DRAFT_RELPATH


async def test_run_returns_the_path_it_actually_wrote(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), draft_root)

    result = await bootstrap.run("repo", 1)

    assert result == draft_root / "repo" / _DRAFT_RELPATH


async def test_run_leaves_the_mirror_worktree_byte_identical(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    before = {path: path.read_bytes() for path in worktree.rglob("*") if path.is_file()}
    mirror = FakeMirror(worktree)
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), tmp_path / "drafts")

    await bootstrap.run("repo", 1)

    after = {path: path.read_bytes() for path in worktree.rglob("*") if path.is_file()}
    assert after == before


async def test_run_twice_replaces_the_previous_draft_in_place(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror, bodies=["BODY-ONE", "BODY-TWO"])
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), draft_root)

    await bootstrap.run("repo", 1)
    await bootstrap.run("repo", 1)

    draft_path = draft_root / "repo" / _DRAFT_RELPATH
    files = [path for path in draft_root.rglob("*") if path.is_file()]
    matching = [path for path in files if "BODY-TWO" in path.read_text(encoding="utf-8")]
    assert matching == [draft_path]
    assert "BODY-ONE" not in draft_path.read_text(encoding="utf-8")


async def test_run_leaves_an_already_reviewed_committed_style_artifact_untouched(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    draft_root = tmp_path / "drafts"
    architecture = draft_root / "repo" / "ARCHITECTURE.md"
    overview = draft_root / "repo" / "docs" / "overview.md"
    architecture.parent.mkdir(parents=True)
    architecture.write_bytes(b"curated architecture bytes")
    overview.parent.mkdir(parents=True)
    overview.write_bytes(b"curated overview bytes")
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), draft_root)

    await bootstrap.run("repo", 1)
    await bootstrap.run("repo", 1)

    assert architecture.read_bytes() == b"curated architecture bytes"
    assert overview.read_bytes() == b"curated overview bytes"


async def test_run_keeps_per_repo_drafts_separate_when_two_repos_share_one_draft_root(
    tmp_path,
) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror, bodies=["BODY-REPO-A", "BODY-REPO-B"])
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), draft_root)

    path_a = await bootstrap.run("repo-a", 1)
    path_b = await bootstrap.run("repo-b", 1)

    assert path_a != path_b
    assert "BODY-REPO-A" in path_a.read_text(encoding="utf-8")
    assert "BODY-REPO-B" in path_b.read_text(encoding="utf-8")


async def test_run_round_trips_non_ascii_distiller_output_as_utf8(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    body = "Функция распознаёт unicode — café, 東京"
    distiller = FakeDistiller(mirror, bodies=[body])
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), draft_root)

    result = await bootstrap.run("repo", 1)

    assert body in result.read_text(encoding="utf-8")


# --- Phase 5: _frame — the unreviewed marker --------------------------------


def test_frame_preserves_the_body_verbatim_after_the_banner(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)
    body = "Arbitrary distilled feature text.\nSecond line."

    framed = bootstrap._frame(body)

    assert framed.endswith(body + "\n")
    assert framed.count(body) == 1
    assert framed.index(body) > framed.index("Bootstrap draft")


def test_frame_still_emits_heading_banner_and_trailing_newline_for_empty_body(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)

    framed = bootstrap._frame("")

    assert "Bootstrap draft" in framed
    assert any(line.startswith("> ") for line in framed.splitlines())
    assert framed.endswith("\n")


async def test_run_writes_exactly_what_frame_produces(tmp_path) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    distiller = FakeDistiller(mirror, bodies=["the distilled body"])
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, distiller, CodeSourceStrategy(), draft_root)

    result = await bootstrap.run("repo", 1)

    assert result.read_text(encoding="utf-8") == bootstrap._frame("the distilled body")


def test_frame_marker_carries_all_three_unreviewed_claims(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)

    framed = bootstrap._frame("any body").lower()

    assert "machine-generated draft" in framed
    assert "not indexed into the knowledge store" in framed
    assert "never be committed as-is" in framed


def test_frame_marker_is_a_blockquote_preceding_the_body(tmp_path) -> None:
    bootstrap = _make_bootstrap(tmp_path)
    body = "the actual distilled body"

    framed = bootstrap._frame(body)

    blockquote_lines = [line for line in framed.splitlines() if line.startswith("> ")]
    assert blockquote_lines != []
    assert framed.index(blockquote_lines[0]) < framed.index(body)


# --- Phase 6: logging --------------------------------------------------------


async def test_run_logs_repo_ref_selected_count_and_draft_path_on_completion(
    tmp_path, caplog
) -> None:
    worktree = _build_mixed_worktree(tmp_path)
    mirror = FakeMirror(worktree)
    draft_root = tmp_path / "drafts"
    bootstrap = CodeBootstrap(mirror, FakeDistiller(mirror), CodeSourceStrategy(), draft_root)

    with caplog.at_level(logging.INFO, logger="src.knowledge.bootstrap"):
        result = await bootstrap.run("repo", 1)

    records = [r for r in caplog.records if r.name == "src.knowledge.bootstrap"]
    assert records != []
    message = records[-1].getMessage()
    assert "repo" in message
    assert "HEAD" in message
    assert "3" in message
    assert str(result) in message
