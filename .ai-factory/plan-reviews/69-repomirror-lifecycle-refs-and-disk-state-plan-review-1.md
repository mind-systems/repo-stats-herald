## Code Review Summary

**Artifact reviewed:** `.ai-factory/plans/69-repomirror-lifecycle-refs-and-disk-state.md` (test plan)
**Governing spec:** `.ai-factory/specs/78-repo-mirror-surface-test-plan.md` (ROADMAP_TESTS.md line 19 — "RepoMirror — lifecycle, refs and disk state")
**Target under test:** `src/github/mirror.py`
**Files Reviewed:** 1 plan + 4 grounding files (mirror source, conftest, existing isolation test, governing spec)
**Risk Level:** 🟡 Medium

The plan is a faithful, near-complete restatement of spec 78's lifecycle group (cases 1–31, 37–38), correctly excluding the credential group (cases 32–36, its own ROADMAP_TESTS line 20 entry) and the concurrency/async surface (20.2.x). Coverage, scope, fixture reuse, and file paths all check out against ground truth. One case, however, carries a **verified-false assumption about git's behavior** that would make the specified test red against correct code — this blocks a clean pass.

### Context Gates
- **Architecture** (`.ai-factory/ARCHITECTURE.md`): OK — test-only plan, no module boundaries touched, adds one file under `tests/github/`, edits no `src/`.
- **Rules** (`.ai-factory/RULES.md`): OK — file is intentionally empty (no project counter-defaults); nothing to violate.
- **Roadmap** (`.ai-factory/ROADMAP_TESTS.md` line 19): OK — plan links to spec 78; scope ("everything except the credential group and concurrency/async") matches the contract line exactly.
- **skill-context** (`.ai-factory/skill-context/aif-review/SKILL.md`): absent — no project-specific review overrides to apply.

### Critical Issues

**1. Task 5, case "should keep reporting the branch captured at clone time when upstream's HEAD moves afterwards" (plan line 72; spec case 18) — the "known limitation" premise is false for `RepoMirror`.**

The case is justified with: *"known limitation — `git fetch --prune` does not update a mirror's local HEAD."* This is **not true for the clone `ensure` actually creates.** `ensure` runs `git clone --mirror` (mirror.py:116), which sets `remote.origin.mirror=true`. With that flag, `git fetch --prune origin` (mirror.py:121–125) **does** follow the upstream's HEAD.

Verified against git 2.50.1 with the exact commands `ensure` issues:
```
clone --mirror:                 mirror HEAD = feature
upstream HEAD -> trunk; fetch:  mirror HEAD = trunk      # followed
upstream HEAD -> feature; fetch:mirror HEAD = feature    # followed back
```
Control — a **non**-mirror bare clone (`remote.origin.mirror` unset) does NOT follow HEAD across a fetch. The "known limitation" in the spec describes non-mirror behavior and misattributes it to `RepoMirror`.

Consequence for the specified test:
- Written as the case description implies (move upstream HEAD, then a second `ensure`/`fetch`, then assert `default_branch` is unchanged at the clone-time branch) → the test is **red against correct code**: after re-`ensure`, `default_branch` returns the *new* upstream branch.
- Written to pass (move upstream HEAD but never fetch, then assert `default_branch` unchanged) → the test is green but **vacuous and mislabeled**: it pins "a HEAD you never refreshed stays stale," not the fetch-vs-HEAD behavior it claims to.

The real, testable behavior is the opposite of what the case asserts: `default_branch` **tracks** upstream's HEAD, refreshed on each `ensure`. Resolution options, in order of preference:
1. Re-point this case to pin the *actual* behavior — after moving upstream HEAD and re-`ensure`ing, `default_branch` returns the new branch — and drop the "known limitation" framing.
2. If the intended contract really is "canonical ref must not drift silently when upstream renames its default," that is a **source-behavior decision** (`ensure` would need `git remote set-head` handling or an explicit HEAD pin), not something a test can assert over today's code — escalate it rather than encoding a red test.

Because this defect lives in the governing spec (case 18) as well as the plan, flag both when resolving; the plan is the artifact the implementer will follow, so it must be corrected here regardless.

### Minor Issues

**2. Task 5, case "should raise rather than return an empty string when the repo was never ensured" (plan line 74; spec case 20) — exception type is `FileNotFoundError`, not `CalledProcessError`.**

When the repo was never `ensure`d, the bare path does not exist, so `default_branch`'s `self._run([...], cwd=self._bare_path(repo), ...)` fails at process spawn (cannot `chdir` into a missing directory) and raises **`FileNotFoundError`**, verified against the real call. This is the one lifecycle case that raises a non-`CalledProcessError`. The plan's convention (line 25) — *"Assert on `subprocess.CalledProcessError` type and `returncode` only"* — is correct for the git-nonzero cases (e.g. Task 4's missing-ref case) but would be **misapplied** here; an implementer defaulting to it writes `pytest.raises(subprocess.CalledProcessError)` and the test fails on the wrong exception. Recommend the plan note that this case raises `FileNotFoundError` (or at minimum "not a `CalledProcessError` — the failure is at process spawn, not a git exit"), so the convention is not applied blindly.

### Positive Notes
- **Complete, correctly-scoped coverage.** All of spec 78's lifecycle cases (1–31, 37–38) map cleanly to the plan's 9 tasks; the credential group (32–36) and concurrency/async (20.2.x) are excluded exactly as the ROADMAP_TESTS line and spec scope-guard require.
- **Deferred-reclamation contract handled correctly** — the plan repeatedly forbids `not path.exists()` right after a `with` block and only asserts absence after the next `ensure`, matching the source docstring's rationale (mirror.py:133–163). This is the single most likely thing a future reader would "fix" wrongly, and the plan pins it well.
- **Disk vs. `git worktree list --porcelain` treated as two independent observables** — correct; metadata and directory state genuinely diverge, and `worktree prune` exists precisely for that.
- **Grounded git facts verified true:** the fixture's HEAD lands on `feature` (default-branch-≠-`main` for free); force-push adoption works via the mirror's `+refs/*:refs/*` refspec; `--prune` drops deleted refs; the `mkdtemp`-before-failing-`worktree add` leak in Task 4's missing-ref case is real and correctly pinned as a decision-on-record.
- **Restart modeled as a fresh `RepoMirror` over the same `mirror_root`** — the only faithful stand-in for the in-memory `_finished_worktrees` list, correctly used for the sweep cases.
- **Non-recursive `glob("*.git")` gap** is called out to document-not-fix, consistent with the flat `clone_source` layout — good judgment on not over-reaching into an `rglob` change without a naming change.
- Fixture-reuse instruction is feasible: `tests` is a proper package (has `__init__.py` throughout), so a locally-built `RepoMirror` test can `from tests.github.conftest import _git, _commit` for pinned committer identity as the spec's gotcha requires.
