"""Drives `EpisodicBackfill` against real fixture git repositories.

`EpisodicBackfill` replays a served repo's full first-parent history,
choosing per historical step whether to derive an episodic entry from the
roadmap (resolver mode) or from changed code blobs (distiller mode), and
appending one entry per step with that step's own historical commit
timestamp. Three hazards drive this suite: the mode must be decided fresh
per historical step rather than once at HEAD, a re-run over an unchanged
repo must append nothing, and every entry's `changed_at` must be the
commit's own committer timestamp rather than the run moment. Every
collaborator except the injected LLM/store/embedder fakes is real —
`GitCommitCollector`, `LinkedChangeResolver`, `CodeDistiller`,
`AiFactorySourceStrategy`, and `CodeSourceStrategy` all run against a plain
`git init` fixture repo, so the per-historical-tree contract is exercised
directly rather than stubbed away.
"""

import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from src.episodic.backfill import EpisodicBackfill
from src.episodic.linked_change import LinkedChangeResolver
from src.episodic.models import EpisodicEntry
from src.episodic.store import EpisodicStore
from src.knowledge.code_distiller import CodeDistiller
from src.knowledge.code_source_strategy import CodeSourceStrategy
from src.knowledge.source_strategy import AiFactorySourceStrategy, SourceStrategy
from src.llm.client import LLMClient
from src.llm.embedder import Embedder

EMBEDDING_DIM = 768
REPO_NAME = "acme/widgets"
ORG_ID = 424242


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


# --- Fakes -------------------------------------------------------------


class FakeMirror:
    """Duck-type of `RepoMirror` exposing only the read-only surface
    `EpisodicBackfill` uses. `object_store_path` returns the fixture repo
    path directly — no bare clone needed since every downstream call shells
    out with `git -C`. `tree` raises unconditionally: backfill's whole point
    is reading blobs by SHA off the object store, never opening a worktree
    per historical step, so a call reaching `tree` is itself a test
    failure."""

    def __init__(self, repo_path: Path, default_branch_name: str = "trunk") -> None:
        self.repo_path = repo_path
        self.default_branch_name = default_branch_name
        self.ensure_calls: list[tuple[str, int]] = []
        self.default_branch_calls: list[str] = []
        self.call_order: list[str] = []

    async def ensure(self, repo: str, org_id: int) -> None:
        self.ensure_calls.append((repo, org_id))
        self.call_order.append("ensure")

    def object_store_path(self, repo: str) -> Path:
        self.call_order.append("object_store_path")
        return self.repo_path

    async def default_branch(self, repo: str) -> str:
        self.default_branch_calls.append(repo)
        self.call_order.append("default_branch")
        return self.default_branch_name

    def tree(self, *args, **kwargs):
        raise AssertionError("EpisodicBackfill must never request a worktree for a historical step")


class FakeEmbedder(Embedder):
    """Records every `texts` argument; always returns one zero vector,
    matching every backfill call site's single-element batch."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.0] * EMBEDDING_DIM]


class FakeLLMClient(LLMClient):
    """Records every prompt it is given; returns a fixed response — flip it
    to a blank/whitespace string to exercise the distiller's fallback."""

    def __init__(self, response: str = "a distilled description") -> None:
        self.prompts: list[str] = []
        self.response = response

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class FakeEpisodicStore(EpisodicStore):
    """In-memory `EpisodicStore`. `recorded_commit_shas` returns the real
    union of every stored entry's `commit_shas` for `repo` — the narrower
    in-run `recorded` set inside `run()` vs. this store read-back is exactly
    what idempotency across two `run()` calls must survive."""

    def __init__(self) -> None:
        self.entries: list[EpisodicEntry] = []

    async def append(self, entry: EpisodicEntry) -> None:
        self.entries.append(entry)

    async def query(self, *args, **kwargs) -> list[EpisodicEntry]:
        raise AssertionError("FakeEpisodicStore.query must not be called by backfill")

    async def recorded_commit_shas(self, repo: str) -> set[str]:
        shas: set[str] = set()
        for entry in self.entries:
            if entry.repo == repo:
                shas.update(entry.commit_shas)
        return shas


@pytest.fixture
def make_backfill():
    """Builds a fully-wired `EpisodicBackfill` over `repo_path`, returning
    `(backfill, mirror, store, embedder, llm)` so a test can inspect any
    collaborator's recorded calls. Every collaborator except the store,
    embedder, and LLM is real."""

    def _make(
        repo_path: Path,
        *,
        default_branch_name: str = "trunk",
        canonical_refs: dict[str, str] | None = None,
        store: EpisodicStore | None = None,
        embedder: FakeEmbedder | None = None,
        llm: FakeLLMClient | None = None,
        source_strategy: SourceStrategy | None = None,
        code_strategy: SourceStrategy | None = None,
    ) -> tuple[EpisodicBackfill, FakeMirror, EpisodicStore, FakeEmbedder, FakeLLMClient]:
        mirror = FakeMirror(repo_path, default_branch_name=default_branch_name)
        collector = GitCommitCollector()
        chosen_source_strategy = source_strategy or AiFactorySourceStrategy()
        resolved_llm = llm if llm is not None else FakeLLMClient()
        resolved_embedder = embedder if embedder is not None else FakeEmbedder()
        resolved_store = store if store is not None else FakeEpisodicStore()

        backfill = EpisodicBackfill(
            mirror=mirror,
            resolver=LinkedChangeResolver(collector, chosen_source_strategy),
            embedder=resolved_embedder,
            store=resolved_store,
            collector=collector,
            canonical_refs=canonical_refs or {},
            distiller=CodeDistiller(resolved_llm),
            code_strategy=code_strategy or CodeSourceStrategy(),
            source_strategy=chosen_source_strategy,
        )
        return backfill, mirror, resolved_store, resolved_embedder, resolved_llm

    return _make


# --- Canonical ref selection ------------------------------------------------


async def test_canonical_ref_uses_override_when_present(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "base", write={"README.md": "base"})
    _git("checkout", "-q", "-b", "feature-a", cwd=git_repo)
    a_sha = commit_snapshot(git_repo, "a change", write={"a.txt": "a"})
    _git("checkout", "-q", "-b", "feature-b", "trunk", cwd=git_repo)
    b_sha = commit_snapshot(git_repo, "b change", write={"b.txt": "b"})

    backfill, mirror, *_ = make_backfill(
        git_repo, default_branch_name="feature-b", canonical_refs={REPO_NAME: "feature-a"}
    )

    ref = await backfill._canonical_ref(REPO_NAME)

    assert ref == "feature-a"
    collector = GitCommitCollector()
    walked_shas = {after for _, after in collector.first_parent_steps(str(git_repo), ref)}
    assert a_sha in walked_shas
    assert b_sha not in walked_shas


async def test_canonical_ref_falls_back_to_default_branch(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "base", write={"README.md": "base"})

    backfill, mirror, *_ = make_backfill(git_repo, default_branch_name="trunk", canonical_refs={})

    ref = await backfill._canonical_ref(REPO_NAME)

    assert ref == "trunk"
    assert mirror.default_branch_calls == [REPO_NAME]


# --- Harness-presence mode boundary -----------------------------------------


def test_harness_present_true_when_roadmap_introduced(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={"ROADMAP.md": "- [ ] 1.1 — do thing\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is True


def test_harness_present_true_when_roadmap_deleted(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"ROADMAP.md": "- [ ] 1.1 — do thing\n"})
    after = commit_snapshot(git_repo, "after", remove=["ROADMAP.md"], write={"src/a.py": "print(1)\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is True


def test_harness_present_false_when_neither_end_has_roadmap(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={"src/a.py": "print(2)\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is False


def test_harness_present_true_for_ai_factory_roadmap_path(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={".ai-factory/ROADMAP.md": "- [ ] 1.1 — thing\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is True


def test_harness_present_false_when_source_strategy_has_no_roadmap_paths(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={"ROADMAP.md": "- [x] 1.1 — thing\n"})

    # `CodeSourceStrategy` in the `source_strategy` slot — guards the
    # argument-order footgun between the two adjacent, same-typed strategy
    # constructor parameters.
    backfill, *_ = make_backfill(git_repo, source_strategy=CodeSourceStrategy())

    assert backfill._harness_present(str(git_repo), before, after) is False


async def test_harness_present_true_for_roadmap_with_no_done_lines(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={"ROADMAP.md": "- [ ] 1.1 — not done yet\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is True

    # Presence, not content, selects the mode: this step still produces a
    # commits-only resolver entry even though no box was ever checked.
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)
    assert entry is not None
    assert entry.completed_tasks == ()


def test_harness_present_false_for_similarly_named_non_candidate_path(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/a.py": "print(1)\n"})
    after = commit_snapshot(git_repo, "after", write={"docs/ROADMAP.md": "- [x] 1.1 — thing\n"})

    backfill, *_ = make_backfill(git_repo)

    assert backfill._harness_present(str(git_repo), before, after) is False


# --- Resolver-mode entry construction ---------------------------------------


async def test_resolve_entry_changed_at_is_historical_not_run_moment(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"ROADMAP.md": "- [ ] 1.1 — task\n"})
    when = "2019-03-14T09:30:00+00:00"
    after = commit_snapshot(git_repo, "after", write={"ROADMAP.md": "- [x] 1.1 — task\n"}, when=when)

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.changed_at == datetime.fromisoformat(when)
    assert entry.changed_at.year != datetime.now(timezone.utc).year


_BEFORE_TASKS = "# Roadmap\n- [x] 1.1 — already done\n- [ ] 1.2 — pending\n"
_AFTER_TASKS = (
    "# Roadmap\n"
    "- [ ] 1.2 — pending\n"
    "  - [x] 1.1 — already done (relocated)\n"
    "- [x] 2.1 — newly done\n"
)


async def test_resolve_entry_completed_tasks_only_new_transitions(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"ROADMAP.md": _BEFORE_TASKS})
    after = commit_snapshot(git_repo, "after", write={"ROADMAP.md": _AFTER_TASKS})

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.completed_tasks == ("2.1",)


async def test_resolve_entry_content_orders_tasks_then_messages(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"ROADMAP.md": "- [ ] 3.1 — pending\n"})
    after = commit_snapshot(
        git_repo, "ship the feature", write={"ROADMAP.md": "- [x] 3.1 — pending\n"}
    )

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    lines = entry.content.split("\n")
    assert lines[0] == "3.1"
    assert lines[-1] == "ship the feature"


async def test_resolve_entry_commit_shas_span_full_merge_range(git_repo, merge_history, make_backfill):
    repo, base_sha, merge_sha = merge_history()
    side_sha = _git("rev-parse", "side", cwd=repo).stdout.strip()

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(repo), base_sha, merge_sha)

    assert entry is not None
    assert side_sha in entry.commit_shas
    assert merge_sha in entry.commit_shas
    assert len(entry.commit_shas) == 3


async def test_resolve_entry_returns_none_when_nothing_to_record(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "", allow_empty_message=True)

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is None


async def test_resolve_entry_embeds_content_as_single_element_batch(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "did the thing")

    backfill, _, _, embedder, _ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert embedder.calls == [[entry.content]]


async def test_resolve_entry_never_calls_the_distiller_or_llm(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "did the thing")

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert llm.prompts == []


async def test_resolve_entry_repo_field_is_the_run_argument_not_the_bare_path(
    git_repo, make_backfill, commit_snapshot
):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "did the thing")

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._resolve_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.repo == REPO_NAME
    assert entry.repo != str(git_repo)


# --- Code-derived entry: selection and temp-tree materialization -----------


async def test_distill_entry_passes_only_selected_paths(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(
        git_repo,
        "add code and docs",
        write={"src/feature/a.py": "def a(): pass\n", "README.md": "not code\n"},
    )

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "src/feature/a.py" in llm.prompts[0]
    assert "def a(): pass" in llm.prompts[0]
    assert "README.md" not in llm.prompts[0]


async def test_distill_entry_excludes_non_code_paths(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(
        git_repo,
        "mixed change",
        write={
            "src/feature/a.py": "value = 1\n",
            "docs/design.md": "design notes\n",
            "tests/test_a.py": "def test_a(): pass\n",
        },
    )

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "src/feature/a.py" in llm.prompts[0]
    assert "docs/design.md" not in llm.prompts[0]
    assert "design notes" not in llm.prompts[0]
    assert "tests/test_a.py" not in llm.prompts[0]


async def test_distill_entry_writes_blob_body_into_temp_tree_before_prompting(
    git_repo, make_backfill, commit_snapshot
):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "add module", write={"src/mod/thing.py": "MARKER_BODY_TEXT = 42\n"})

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "MARKER_BODY_TEXT = 42" in llm.prompts[0]


async def test_distill_entry_issues_one_prompt_per_module(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(
        git_repo,
        "touch two modules",
        write={
            "src/mod_a/one.py": "a = 1\n",
            "src/mod_a/two.py": "a2 = 2\n",
            "src/mod_b/one.py": "b = 1\n",
        },
    )

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 2


async def test_distill_entry_skips_deleted_path_and_distills_remaining(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before", write={"src/mod/gone.py": "gone = 1\n"})
    after = commit_snapshot(
        git_repo,
        "remove one, add another",
        write={"src/mod/kept.py": "kept = 1\n"},
        remove=["src/mod/gone.py"],
    )

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "src/mod/kept.py" in llm.prompts[0]
    assert "gone.py" not in llm.prompts[0]


async def test_distill_entry_skips_non_utf8_blob_and_distills_remaining(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(
        git_repo,
        "add binary and text",
        write={
            "src/mod/bin.py": b"\xff\xfe\x00broken",
            "src/mod/text.py": "text_marker = 1\n",
        },
    )

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "text_marker" in llm.prompts[0]


async def test_distill_entry_recreates_nested_directories(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "add deeply nested file", write={"src/a/b/c/deep.py": "deep_marker = 1\n"})

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "deep_marker" in llm.prompts[0]


async def test_distill_entry_treats_root_commit_paths_as_added(git_repo, make_backfill, commit_snapshot):
    after = commit_snapshot(git_repo, "root commit", write={"src/mod/root.py": "root_marker = 1\n"})

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), EMPTY_TREE_SHA, after)

    assert entry is not None
    assert len(llm.prompts) == 1
    assert "root_marker" in llm.prompts[0]


async def test_distill_entry_leaves_no_temp_directory_behind(
    git_repo, make_backfill, commit_snapshot, tmp_path, monkeypatch
):
    subdir = tmp_path / "tmp_base"
    subdir.mkdir()
    # `gettempdir()` caches into `tempfile.tempdir` on first use, so setting
    # only `TMPDIR` may not take effect if `tempfile` was already
    # initialized this session — patch the module attribute directly.
    monkeypatch.setattr(tempfile, "tempdir", str(subdir))

    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "add file", write={"src/mod/x.py": "x = 1\n"})

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert list(subdir.iterdir()) == []


# --- Code-derived entry: fallbacks and timestamp ----------------------------


async def test_distill_entry_falls_back_to_commit_messages_when_no_code_selected(
    git_repo, make_backfill, commit_snapshot
):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "docs only change", write={"README.md": "just docs\n"})

    backfill, _, _, _, llm = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.content == "docs only change"
    assert llm.prompts == []


async def test_distill_entry_falls_back_when_distiller_returns_whitespace(
    git_repo, make_backfill, commit_snapshot
):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(git_repo, "add whitespace-described code", write={"src/mod/x.py": "x = 1\n"})

    backfill, _, _, _, llm = make_backfill(git_repo, llm=FakeLLMClient(response="   \n\t  "))
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.content == "add whitespace-described code"
    assert len(llm.prompts) == 1


async def test_distill_entry_returns_none_when_nothing_to_record(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    after = commit_snapshot(
        git_repo, "", write={"README.md": "no code here\n"}, allow_empty_message=True
    )

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is None


async def test_distill_entry_sets_empty_tasks_and_historical_timestamp(git_repo, make_backfill, commit_snapshot):
    before = commit_snapshot(git_repo, "before")
    when = "2018-06-01T12:00:00+00:00"
    after = commit_snapshot(git_repo, "add code", write={"src/mod/x.py": "x = 1\n"}, when=when)

    backfill, *_ = make_backfill(git_repo)
    entry = await backfill._distill_entry(REPO_NAME, ORG_ID, str(git_repo), before, after)

    assert entry is not None
    assert entry.completed_tasks == ()
    assert entry.changed_at == datetime.fromisoformat(when)
    assert entry.changed_at.year != datetime.now(timezone.utc).year


# --- run(): mode selection across a mixed history ---------------------------


_ROADMAP_V1 = "- [x] 1.1 — first\n"
_ROADMAP_V2 = "- [x] 1.1 — first\n- [x] 2.1 — second\n"
_ROADMAP_V3 = "- [x] 1.1 — first\n- [x] 2.1 — second\n- [x] 3.1 — third\n"


def _build_mixed_roadmap_history(git_repo: Path, commit_snapshot) -> None:
    """Commits 1-2 touch only `src/*.py` (no roadmap exists yet); commit 3
    introduces `ROADMAP.md` with one done task; commits 4-5 flip one more
    box each. Five first-parent steps: 2 must derive from code, 3 from the
    resolver, with the mode flipping exactly once at the introducing step."""
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "commit 2", write={"src/mod/b.py": "b = 1\n"})
    commit_snapshot(git_repo, "commit 3", write={"ROADMAP.md": _ROADMAP_V1})
    commit_snapshot(git_repo, "commit 4", write={"ROADMAP.md": _ROADMAP_V2})
    commit_snapshot(git_repo, "commit 5", write={"ROADMAP.md": _ROADMAP_V3})


async def test_run_appends_one_entry_per_commit_including_root(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "root", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "second", write={"src/mod/b.py": "b = 1\n"})
    commit_snapshot(git_repo, "third", write={"src/mod/c.py": "c = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 3


async def test_run_splits_code_and_resolver_modes_across_mixed_history(git_repo, make_backfill, commit_snapshot):
    _build_mixed_roadmap_history(git_repo, commit_snapshot)

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    ordered = sorted(store.entries, key=lambda e: e.changed_at)
    assert len(ordered) == 5
    is_code_derived = [entry.completed_tasks == () for entry in ordered]
    assert is_code_derived == [True, True, False, False, False]


async def test_run_invokes_llm_only_for_pre_roadmap_steps(git_repo, make_backfill, commit_snapshot):
    _build_mixed_roadmap_history(git_repo, commit_snapshot)

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    # A once-at-HEAD mode evaluation would see HEAD's roadmap and treat
    # every step as resolver-mode, issuing zero LLM calls. Per-step
    # evaluation issues exactly one LLM call per pre-roadmap step.
    assert len(llm.prompts) == 2


async def test_run_derives_every_entry_from_code_with_no_roadmap_ever(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "commit 2", write={"src/mod/b.py": "b = 1\n"})
    commit_snapshot(git_repo, "commit 3", write={"src/mod/c.py": "c = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 3
    assert all(entry.completed_tasks == () for entry in store.entries)
    assert len(llm.prompts) == 3


async def test_run_derives_every_entry_via_resolver_when_roadmap_from_first_commit(
    git_repo, make_backfill, commit_snapshot
):
    commit_snapshot(git_repo, "commit 1", write={"ROADMAP.md": "- [x] 1.1 — first\n"})
    commit_snapshot(git_repo, "commit 2", write={"ROADMAP.md": "- [x] 1.1 — first\n- [x] 2.1 — second\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2
    assert llm.prompts == []


async def test_run_walks_only_first_parent_when_side_branch_merged(git_repo, merge_history, make_backfill):
    repo, base_sha, merge_sha = merge_history()
    side_sha = _git("rev-parse", "side", cwd=repo).stdout.strip()

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 3
    merge_step_entries = [entry for entry in store.entries if side_sha in entry.commit_shas]
    assert len(merge_step_entries) == 1
    assert merge_sha in merge_step_entries[0].commit_shas
    assert [entry for entry in store.entries if entry.commit_shas == (side_sha,)] == []


# --- run(): idempotency, guards, and logging --------------------------------


async def test_run_second_run_over_unchanged_repo_appends_nothing(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "commit 2", write={"ROADMAP.md": "- [x] 1.1 — first\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    entries_after_first_run = list(store.entries)
    embed_calls_after_first_run = list(embedder.calls)
    llm_prompts_after_first_run = list(llm.prompts)

    await backfill.run(REPO_NAME, ORG_ID)

    assert store.entries == entries_after_first_run
    assert embedder.calls == embed_calls_after_first_run
    assert llm.prompts == llm_prompts_after_first_run


async def test_run_appends_only_new_commits_landed_between_runs(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)
    assert len(store.entries) == 1

    commit_snapshot(git_repo, "commit 2", write={"src/mod/b.py": "b = 1\n"})
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2


async def test_run_skips_step_already_recorded_by_a_live_push(git_repo, make_backfill, commit_snapshot):
    sha1 = commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    sha2 = commit_snapshot(git_repo, "commit 2", write={"src/mod/b.py": "b = 1\n"})

    seeded_store = FakeEpisodicStore()
    seeded_store.entries.append(
        EpisodicEntry(
            repo=REPO_NAME,
            org_id=ORG_ID,
            completed_tasks=(),
            commit_shas=(sha1,),
            content="live push already recorded this",
            embedding=[0.0] * EMBEDDING_DIM,
            changed_at=datetime.now(timezone.utc),
        )
    )

    backfill, mirror, store, embedder, llm = make_backfill(git_repo, store=seeded_store)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2
    new_entries = [entry for entry in store.entries if entry.content != "live push already recorded this"]
    assert len(new_entries) == 1
    assert new_entries[0].commit_shas == (sha2,)


async def test_run_calls_ensure_before_reading_object_store_path(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert mirror.call_order.index("ensure") < mirror.call_order.index("object_store_path")


async def test_run_never_requests_a_worktree_for_any_historical_step(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "commit 2", write={"ROADMAP.md": "- [x] 1.1 — first\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    # `FakeMirror.tree()` raises unconditionally — this only completes if
    # backfill never calls it for either the code- or resolver-mode step.
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2


async def test_run_completes_without_raising_when_canonical_ref_missing(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo, default_branch_name="does-not-exist")
    await backfill.run(REPO_NAME, ORG_ID)

    assert store.entries == []


async def test_run_appends_nothing_for_a_repo_with_an_unborn_head(git_repo, make_backfill):
    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert store.entries == []


async def test_run_logs_walked_appended_skipped_counts(git_repo, make_backfill, commit_snapshot, caplog):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    # An empty-message, no-code-change step: yields neither distilled text
    # nor message text -> `_distill_entry` returns `None` -> counted as
    # skipped, not appended.
    commit_snapshot(git_repo, "", allow_empty_message=True)
    commit_snapshot(git_repo, "commit 3", write={"src/mod/b.py": "b = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    with caplog.at_level(logging.INFO, logger="src.episodic.backfill"):
        await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2
    assert "commits_walked=3" in caplog.text
    assert "entries_appended=2" in caplog.text
    assert "skipped=1" in caplog.text


async def test_run_embeds_once_per_appended_entry_and_never_for_skipped(git_repo, make_backfill, commit_snapshot):
    commit_snapshot(git_repo, "commit 1", write={"src/mod/a.py": "a = 1\n"})
    commit_snapshot(git_repo, "", allow_empty_message=True)
    commit_snapshot(git_repo, "commit 3", write={"src/mod/b.py": "b = 1\n"})

    backfill, mirror, store, embedder, llm = make_backfill(git_repo)
    await backfill.run(REPO_NAME, ORG_ID)

    assert len(store.entries) == 2
    assert len(embedder.calls) == 2
