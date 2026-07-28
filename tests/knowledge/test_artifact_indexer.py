from pathlib import Path

import pytest

from src.knowledge.chunker import chunk_markdown
from src.knowledge.indexer import ArtifactIndexer
from src.knowledge.source_strategy import AiFactorySourceStrategy, SourceStrategy
from src.knowledge.store import Chunk, KnowledgeStore
from src.llm.embedder import Embedder

# Three top-level `##` sections (no `#`), so `chunk_markdown` splits it into
# three position-distinguishable chunks — used to pin ordering and pairing.
DOC = """## Section One

Body one paragraph.

## Section Two

Body two paragraph.

## Section Three

Body three paragraph.
"""


def _write(tree: Path, path: str, content: str) -> None:
    file_path = tree / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


class FakeSourceStrategy(SourceStrategy):
    """Selects exactly the configured path set (or via a predicate) and
    records every repo-relative `path` it was consulted with, so gate tests
    can assert the indexer routed the decision through it rather than
    deciding on its own."""

    def __init__(self, selected: set[str] | None = None, predicate=None) -> None:
        self._selected = selected or set()
        self._predicate = predicate
        self.calls: list[str] = []

    def selects(self, path: str) -> bool:
        self.calls.append(path)
        if self._predicate is not None:
            return self._predicate(path)
        return path in self._selected


class FakeEmbedder(Embedder):
    """Returns position-distinct vectors (`[[float(i)] for i, _ in
    enumerate(texts)]`) so a reorder or off-by-one bug in the pairing is
    visible; a single-vector fake would hide it. `vector_count` deliberately
    returns a mismatched vector count when given; `error` raises instead of
    returning. Tolerates `embed([])`."""

    def __init__(
        self,
        vector_count: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self._vector_count = vector_count
        self._error = error
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self._error is not None:
            raise self._error
        count = len(texts) if self._vector_count is None else self._vector_count
        return [[float(i)] for i in range(count)]


class FakeKnowledgeStore(KnowledgeStore):
    """Records every `upsert`/`delete` call verbatim; `query` returns `[]`
    since no test here exercises retrieval. `error`, when set, raises
    instead of recording on `upsert` — the store-failure propagation
    case."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.upserts: list[tuple[str, str, list[Chunk]]] = []
        self.deletes: list[tuple[str, str]] = []

    async def upsert(self, repo: str, path: str, items: list[Chunk]) -> None:
        if self._error is not None:
            raise self._error
        self.upserts.append((repo, path, items))

    async def delete(self, repo: str, path: str) -> None:
        self.deletes.append((repo, path))

    async def query(self, embedding: list[float], k: int, repo: str | None = None) -> list[Chunk]:
        return []


# --- Phase 1: `index` — the selection gate ---------------------------------


async def test_upserts_the_files_chunks_when_the_strategy_selects_the_path(tmp_path: Path) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert len(store.upserts) == 1
    repo, path, _ = store.upserts[0]
    assert (repo, path) == ("org/repo", "CLAUDE.md")


async def test_performs_no_read_no_embed_and_no_upsert_when_the_strategy_does_not_select_the_path(
    tmp_path: Path,
) -> None:
    path = ".ai-factory/plans/17-x.md"
    _write(tmp_path, path, "# Plan\n\nSome orchestrator noise.\n")
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", path, tmp_path)

    assert embedder.calls == []
    assert store.upserts == []


async def test_leaves_the_store_completely_untouched_with_no_delete_for_a_non_selected_path(
    tmp_path: Path,
) -> None:
    path = ".ai-factory/plans/17-x.md"
    _write(tmp_path, path, "# Plan\n\nSome orchestrator noise.\n")
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", path, tmp_path)

    assert store.deletes == []
    assert store.upserts == []


async def test_routes_the_decision_through_the_injected_strategy_rather_than_built_in_path_knowledge(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "src/main.py", "print('hi')\n")
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"src/main.py"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "src/main.py", tmp_path)
    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    indexed_paths = [path for _, path, _ in store.upserts]
    assert indexed_paths == ["src/main.py"]
    assert "src/main.py" in strategy.calls
    assert "CLAUDE.md" in strategy.calls


SELECTED_EXEMPLARS = [
    "CLAUDE.md",
    ".ai-factory/ARCHITECTURE.md",
    ".ai-factory/specs/03-x.md",
]
NOT_SELECTED_EXEMPLARS = [
    ".ai-factory/plan-reviews/01-x.md",
    ".ai-factory/handoffs/02-x.md",
    "src/main.py",
]


@pytest.mark.parametrize("path", SELECTED_EXEMPLARS)
async def test_indexes_governing_artifacts_across_spec_07_exemplars(tmp_path: Path, path: str) -> None:
    _write(tmp_path, path, DOC)
    strategy = AiFactorySourceStrategy()
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", path, tmp_path)

    assert len(store.upserts) == 1


@pytest.mark.parametrize("path", NOT_SELECTED_EXEMPLARS)
async def test_skips_orchestrator_noise_across_spec_07_exemplars(tmp_path: Path, path: str) -> None:
    _write(tmp_path, path, DOC)
    strategy = AiFactorySourceStrategy()
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", path, tmp_path)

    assert len(store.upserts) == 0


# --- Phase 2: `index` — chunk → embed → upsert wiring -----------------------


async def test_sends_every_chunk_to_the_embedder_in_document_order_in_a_single_batch_call(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert len(embedder.calls) == 1
    assert embedder.calls[0] == chunk_markdown(DOC)


async def test_pairs_each_chunks_content_with_the_embedding_returned_at_the_same_position(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    chunks = chunk_markdown(DOC)
    expected_vectors = [[float(i)] for i in range(len(chunks))]
    _, _, items = store.upserts[0]
    assert [(item.content, item.embedding) for item in items] == list(
        zip(chunks, expected_vectors, strict=True)
    )


async def test_preserves_chunk_order_in_the_upserted_item_list(tmp_path: Path) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    _, _, items = store.upserts[0]
    assert [item.content for item in items] == chunk_markdown(DOC)


# --- Phase 2: `index` — key, source tree and re-index -----------------------


async def test_upserts_under_the_exact_repo_path_it_was_handed(tmp_path: Path) -> None:
    nested_path = ".ai-factory/specs/03-x.md"
    _write(tmp_path, nested_path, DOC)
    strategy = FakeSourceStrategy(selected={nested_path})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("acme/widgets", nested_path, tmp_path)

    repo, path, _ = store.upserts[0]
    assert repo == "acme/widgets"
    assert path == nested_path


async def test_reads_the_file_from_the_tree_it_was_given(tmp_path: Path) -> None:
    tree_a = tmp_path / "a"
    tree_b = tmp_path / "b"
    tree_a.mkdir()
    tree_b.mkdir()
    _write(tree_a, "CLAUDE.md", "## Section\n\nFrom tree A.\n")
    _write(tree_b, "CLAUDE.md", "## Section\n\nFrom tree B.\n")
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tree_b)

    _, _, items = store.upserts[0]
    assert "From tree B." in items[0].content
    assert "From tree A." not in items[0].content


async def test_upserts_the_newly_read_content_when_the_same_path_is_re_indexed(tmp_path: Path) -> None:
    _write(tmp_path, "CLAUDE.md", "## Section\n\nFirst version.\n")
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)
    _write(tmp_path, "CLAUDE.md", "## Section\n\nSecond version.\n")
    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert len(store.upserts) == 2
    _, _, items = store.upserts[1]
    assert "Second version." in items[0].content


# --- Phase 3: `index` — degenerate and error paths --------------------------


@pytest.mark.parametrize("content", ["", "   \n\n\t  "])
async def test_still_calls_upsert_with_an_empty_item_list_when_the_file_is_empty_or_whitespace_only(
    tmp_path: Path, content: str
) -> None:
    _write(tmp_path, "CLAUDE.md", content)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert store.upserts == [("org/repo", "CLAUDE.md", [])]


async def test_skips_without_touching_the_store_when_the_file_is_not_valid_utf8(tmp_path: Path) -> None:
    path = "CLAUDE.md"
    (tmp_path / path).write_bytes(b"\xff\xfe\x00\x01binary")
    strategy = FakeSourceStrategy(selected={path})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", path, tmp_path)

    assert store.upserts == []
    assert store.deletes == []


async def test_propagates_filenotfounderror_when_a_selected_path_is_absent_from_the_tree(
    tmp_path: Path,
) -> None:
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    with pytest.raises(FileNotFoundError):
        await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert store.upserts == []


async def test_returns_quietly_when_a_non_selected_path_is_absent_from_the_tree(tmp_path: Path) -> None:
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.index("org/repo", "missing.md", tmp_path)

    assert store.upserts == []


async def test_raises_and_upserts_nothing_when_the_embedder_returns_a_different_number_of_vectors_than_chunks(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    chunk_count = len(chunk_markdown(DOC))
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder(vector_count=chunk_count - 1)
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    with pytest.raises(ValueError):
        await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert store.upserts == []


async def test_propagates_an_embedder_failure_without_upserting(tmp_path: Path) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder(error=RuntimeError("embed failed"))
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    with pytest.raises(RuntimeError):
        await indexer.index("org/repo", "CLAUDE.md", tmp_path)

    assert store.upserts == []


async def test_propagates_a_store_failure_to_the_caller(tmp_path: Path) -> None:
    _write(tmp_path, "CLAUDE.md", DOC)
    strategy = FakeSourceStrategy(selected={"CLAUDE.md"})
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore(error=RuntimeError("store failed"))
    indexer = ArtifactIndexer(strategy, embedder, store)

    with pytest.raises(RuntimeError):
        await indexer.index("org/repo", "CLAUDE.md", tmp_path)


# --- Phase 4: `remove` -------------------------------------------------------


async def test_deletes_exactly_the_given_repo_path_from_the_store() -> None:
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.remove("org/repo", "CLAUDE.md")

    assert store.deletes == [("org/repo", "CLAUDE.md")]


async def test_deletes_unconditionally_without_consulting_the_strategy() -> None:
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.remove("org/repo", ".ai-factory/plans/17-x.md")

    assert store.deletes == [("org/repo", ".ai-factory/plans/17-x.md")]
    assert strategy.calls == []


async def test_does_not_embed_or_upsert_on_remove() -> None:
    strategy = FakeSourceStrategy(selected=set())
    embedder = FakeEmbedder()
    store = FakeKnowledgeStore()
    indexer = ArtifactIndexer(strategy, embedder, store)

    await indexer.remove("org/repo", "CLAUDE.md")

    assert embedder.calls == []
    assert store.upserts == []
