"""Red tests pinning `LinkedChangeResolver.resolve`'s completion semantics
against the stub.

Every test below calls `resolver.resolve(...)` and asserts on the returned
`LinkedChange` as if the resolver were already implemented; each fails
because `resolve` raises `NotImplementedError` (the set-difference logic is
absent), never because of an import, fixture, or git-plumbing error. The
follow-up task's set-difference implementation turns these green unchanged.
"""

from src.commits.models import CommitContext
from src.episodic.linked_change import LinkedChange

_BEFORE_GENUINE = """# Roadmap

### Phase 4
- [x] **4.1.1 — Episodic store contract**
- [ ] **4.2.1 — Linked-change contract**
"""

_AFTER_GENUINE = """# Roadmap

### Phase 4
- [x] **4.1.1 — Episodic store contract**
- [x] **4.2.1 — Linked-change contract**
"""


def test_genuine_become_done_task_is_captured(roadmap_history, resolver):
    repo, shas = roadmap_history(
        [
            ("ROADMAP.md", _BEFORE_GENUINE),
            ("ROADMAP.md", _AFTER_GENUINE),
        ]
    )
    before, after = shas

    result = resolver.resolve(str(repo), before, after)

    assert isinstance(result, LinkedChange)
    assert "4.2.1" in result.completed_tasks
    assert "4.1.1" not in result.completed_tasks


_BEFORE_RELOCATED = """# Roadmap

### Phase 4
- [x] **4.1.1 — Episodic store contract**
- [ ] **4.2.1 — Linked-change contract**
"""

# Same `4.1.1` identifier, but the line moved to a different position,
# was re-indented, and its description was reworded. A raw "+[x]" diff
# would show this as an added line and miscount it as newly completed.
_AFTER_RELOCATED = """# Roadmap

### Phase 4 — Episodic memory
- [ ] **4.2.1 — Linked-change contract**
  - [x] **4.1.1 — Episodic store contract (now with schema notes)**
"""


def test_relocated_already_done_line_is_not_a_false_positive(roadmap_history, resolver):
    repo, shas = roadmap_history(
        [
            ("ROADMAP.md", _BEFORE_RELOCATED),
            ("ROADMAP.md", _AFTER_RELOCATED),
        ]
    )
    before, after = shas

    result = resolver.resolve(str(repo), before, after)

    assert isinstance(result, LinkedChange)
    assert "4.1.1" not in result.completed_tasks
    assert result.completed_tasks == ()


_BEFORE_AI_FACTORY_PATH = """# Roadmap

### Phase 4
- [ ] **4.2.1 — Linked-change contract**
"""

_AFTER_AI_FACTORY_PATH = """# Roadmap

### Phase 4
- [x] **4.2.1 — Linked-change contract**
"""


def test_roadmap_path_comes_from_the_source_strategy(roadmap_history, resolver):
    # Roadmap lives ONLY under `.ai-factory/ROADMAP.md`, never at the repo
    # root — a resolver hardcoded to root `ROADMAP.md` would never find the
    # transition below and would leave `completed_tasks` empty.
    repo, shas = roadmap_history(
        [
            (".ai-factory/ROADMAP.md", _BEFORE_AI_FACTORY_PATH),
            (".ai-factory/ROADMAP.md", _AFTER_AI_FACTORY_PATH),
        ]
    )
    before, after = shas

    result = resolver.resolve(str(repo), before, after)

    assert isinstance(result, LinkedChange)
    assert "4.2.1" in result.completed_tasks


def test_no_roadmap_falls_back_to_commits_only(roadmap_history, resolver):
    repo, shas = roadmap_history(
        [
            (None, ""),
            (None, ""),
        ]
    )
    before, after = shas

    result = resolver.resolve(str(repo), before, after)

    assert isinstance(result, LinkedChange)
    assert result.completed_tasks == ()
    assert isinstance(result.commits, CommitContext)
    assert len(result.commits.commits) > 0


def test_merge_commit_range_resolves_without_error(merge_history, resolver):
    repo, base_sha, merge_sha = merge_history()

    result = resolver.resolve(str(repo), base_sha, merge_sha)

    assert isinstance(result, LinkedChange)
    assert isinstance(result.completed_tasks, tuple)
    assert isinstance(result.commits, CommitContext)


def test_empty_range_resolves_without_error(roadmap_history, resolver):
    repo, shas = roadmap_history([("ROADMAP.md", _BEFORE_GENUINE)])
    (only_sha,) = shas

    result = resolver.resolve(str(repo), only_sha, only_sha)

    assert isinstance(result, LinkedChange)
    assert result.completed_tasks == ()
    assert isinstance(result.commits, CommitContext)
