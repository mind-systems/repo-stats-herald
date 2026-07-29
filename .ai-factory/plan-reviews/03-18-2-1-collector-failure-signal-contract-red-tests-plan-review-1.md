## Code Review Summary

**Files Reviewed:** 1 plan (targets `src/commits/collector.py`, `tests/commits/test_collector.py`)
**Risk Level:** 🟢 Low

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md` / project CLAUDE.md): PASS. The plan adds a module-level exception on `src/commits/collector.py`, the same file that already owns `GitCommitCollector` and `EMPTY_TREE_SHA`. No feature-to-feature dependency is introduced, no composition-root wiring changes — consistent with the feature-modular pattern. `Versioner` is explicitly left untouched, respecting the module boundary.
- **Rules** (`.ai-factory/RULES.md`): PASS. The file carries no counter-default rules; nothing to violate.
- **Global convention** (interface/kind marker): PASS. The plan names the type `CommitCollectionError`, carrying Python's exception kind marker (`Error` suffix), and its Decision section calls this out explicitly.
- **Roadmap** (`.ai-factory/ROADMAP.md` line 18.2.1 → spec `.ai-factory/specs/65-collector-failure-signal-contract.md`): PASS. The plan matches the contract line and the spec on every load-bearing point: settle the fork, declare-not-wire, three cases restated to assert genuine-empty still yields empty, one new red case for a `git` failure, `Versioner._next_staging` untouched, docstring deliberately left describing today's no-raise behavior.
- **Skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific overrides to apply.

### Critical Issues
None.

### Verified points
- **Red-test failure mode is real.** I reproduced the exact `git rev-list` shape the method runs (`rev-list --no-merges --end-of-options <sha>..<sha> ^no-such-branch`) against a fresh one-commit repo: git prints `fatal: bad revision '^no-such-branch'` and exits `128`. The unchanged `new_commits` body hits `if result.returncode != 0: return ()`, so today it returns `()` rather than raising — `pytest.raises(CommitCollectionError)` will see no exception and the case is genuinely red, as the plan intends. The redness is caused by the intended mechanism (non-zero exit swallowed), not by an incidental error, so it is not a false-red.
- **Fixtures exist and match the call.** `git_repo` (default branch `main`) and `commit_at(repo, message) -> sha` are provided by `tests/commits/conftest.py` exactly as the plan uses them. `"no-such-branch"` is genuinely unresolvable in that repo, so the failure is driven the way the plan claims.
- **Existing three cases stay valid.** `test_new_commits_empty_for_fast_forward_back_merge`, `test_new_commits_empty_for_merge_commit_back_merge`, and `test_new_commits_returns_staging_unique_non_merge_commits` assert `() `/`(staging_sha,)`; the plan keeps their git setup and assertions and only adds a clarifying comment, satisfying the spec's "restate against the settled contract" without weakening detection.
- **Import surface is correct.** The test imports `CommitCollectionError` from `src.commits.collector`; the plan defines it module-level in that file, so the import resolves. No `errors` submodule exists in `src/commits/`, and no other `*Error` class exists in `src/` to collide with or reuse — a fresh module-level exception is the idiomatic placement.
- **Scope guard is honored.** Only the declaration lands; body, docstring, and consumers are untouched, so prose and code do not disagree at this step (the docstring's "no-raise" claim still matches the unchanged body). The green wiring is correctly deferred to 18.2.2.

### Positive Notes
- The Decision section makes the fork resolution explicit and argues it against the two rejected alternatives (sentinel / `Optional`) on the grounds that an exception cannot be silently re-collapsed into the falsy `if not new_commits(...)` check — a sound, well-reasoned default for an intentionally-open spec fork.
- The plan is precise about which lines must NOT change (body, `check=False`/`return ()`, docstring, `Versioner`), which keeps the red-test intent from leaking into premature implementation.
- The red-case docstring explicitly labels the redness as the deliverable, so a downstream implement-review will not misread the failing test as a regression.

PLAN_REVIEW_PASS
